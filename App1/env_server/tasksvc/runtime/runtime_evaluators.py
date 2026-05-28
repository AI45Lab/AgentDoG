import copy
import ast
import json

from tasksvc.runtime.reward_health import final_success_only_reward_enabled


class RuntimeRuleEvaluator:
    def _iter_subtree_dicts(self, node, max_depth=6):
        def _walk(value, depth):
            if depth > max_depth:
                return
            if isinstance(value, dict):
                yield value
                for child in value.values():
                    yield from _walk(child, depth + 1)
                return
            if isinstance(value, list):
                for child in value:
                    yield from _walk(child, depth + 1)

        yield from _walk(node, 0)

    def _iter_subtree_strings(self, node, max_depth=6):
        def _walk(value, depth):
            if depth > max_depth:
                return
            if isinstance(value, str):
                yield value
                return
            if isinstance(value, dict):
                for child in value.values():
                    yield from _walk(child, depth + 1)
                return
            if isinstance(value, list):
                for child in value:
                    yield from _walk(child, depth + 1)

        yield from _walk(node, 0)

    def _subtree_root(self, episode, root_key, *, initial=False):
        state_key = "initial_state" if initial else "state"
        state = episode.get(state_key, {}) or {}
        return state.get(root_key)

    def _record_fingerprint(self, value):
        try:
            return json.dumps(value, ensure_ascii=False, sort_keys=True)
        except Exception:
            return repr(value)

    def _normalize_text(self, value):
        if value is None:
            return ""
        return str(value).casefold()

    def _coerce_json_like(self, value):
        if not isinstance(value, str):
            return value
        text = value.strip()
        if not text or text[0] not in "[{":
            return value
        try:
            return json.loads(text)
        except Exception:
            try:
                return ast.literal_eval(text)
            except Exception:
                return value

    def _coerce_numeric(self, value):
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value
        if not isinstance(value, str):
            return value
        text = value.strip()
        if not text:
            return value
        text = text.replace(",", "")
        try:
            if any(token in text for token in (".", "e", "E")):
                return float(text)
            return int(text)
        except Exception:
            return value

    def _coerce_for_comparison(self, actual, expected):
        actual = self._coerce_json_like(actual)
        expected = self._coerce_json_like(expected)
        if isinstance(expected, (list, dict)):
            actual = self._coerce_json_like(actual)
        if isinstance(actual, (int, float)) or isinstance(expected, (int, float)):
            actual = self._coerce_numeric(actual)
            expected = self._coerce_numeric(expected)
        return actual, expected

    def _contains_all_ci(self, actual, needles):
        if isinstance(actual, str):
            normalized = self._normalize_text(actual)
            return all(isinstance(needle, str) and self._normalize_text(needle) in normalized for needle in needles)
        if isinstance(actual, list):
            normalized_values = [self._normalize_text(item) for item in actual]
            return all(
                isinstance(needle, str) and any(self._normalize_text(needle) == value for value in normalized_values)
                for needle in needles
            )
        return False

    def _contains_any_ci(self, actual, needles):
        if isinstance(actual, str):
            normalized = self._normalize_text(actual)
            return any(isinstance(needle, str) and self._normalize_text(needle) in normalized for needle in needles)
        if isinstance(actual, list):
            normalized_values = [self._normalize_text(item) for item in actual]
            return any(
                isinstance(needle, str) and any(self._normalize_text(needle) == value for value in normalized_values)
                for needle in needles
            )
        return False

    def _read_path(self, mapping, path):
        value = mapping
        for part in str(path).split("."):
            if isinstance(value, list):
                try:
                    index = int(part)
                except ValueError:
                    return None
                if index < 0:
                    index += len(value)
                if index < 0 or index >= len(value):
                    return None
                value = value[index]
                continue
            if not isinstance(value, dict) or part not in value:
                return None
            value = value[part]
        return value

    def _resolve_expected(self, episode, expected):
        if isinstance(expected, dict) and "from_success_spec" in expected:
            return episode.get("success_spec", {}).get(expected["from_success_spec"])
        return expected

    def _matches_placeholder_expected(self, actual, expected):
        if expected == "$content":
            return isinstance(actual, str) and bool(actual.strip())
        if isinstance(expected, str) and expected.strip() in {"...", "<any>", "$any_non_empty"}:
            return isinstance(actual, str) and bool(actual.strip())
        return False

    def _matches_operator_expected(self, actual, expected):
        if not isinstance(expected, dict):
            return False
        actual = self._coerce_json_like(actual)
        if "$startswith" in expected:
            prefix = expected.get("$startswith")
            return isinstance(actual, str) and isinstance(prefix, str) and actual.startswith(prefix)
        if "$contains" in expected:
            needle = expected.get("$contains")
            if isinstance(actual, str):
                return isinstance(needle, str) and needle in actual
            if isinstance(actual, list):
                return needle in actual
            return False
        if "$contains_all" in expected:
            needles = expected.get("$contains_all") or []
            if isinstance(actual, str):
                return all(isinstance(needle, str) and needle in actual for needle in needles)
            if isinstance(actual, list):
                return all(needle in actual for needle in needles)
            return False
        if "$contains_any" in expected:
            needles = expected.get("$contains_any") or []
            if isinstance(actual, str):
                return any(isinstance(needle, str) and needle in actual for needle in needles)
            if isinstance(actual, list):
                return any(needle in actual for needle in needles)
            return False
        if "$contains_ci" in expected:
            needle = expected.get("$contains_ci")
            if isinstance(actual, str):
                return isinstance(needle, str) and self._normalize_text(needle) in self._normalize_text(actual)
            if isinstance(actual, list):
                return isinstance(needle, str) and any(self._normalize_text(item) == self._normalize_text(needle) for item in actual)
            return False
        if "$equals_ci" in expected:
            needle = expected.get("$equals_ci")
            return isinstance(actual, str) and isinstance(needle, str) and self._normalize_text(actual) == self._normalize_text(needle)
        if "$contains_all_ci" in expected:
            needles = expected.get("$contains_all_ci") or []
            return self._contains_all_ci(actual, needles)
        if "$contains_any_ci" in expected:
            needles = expected.get("$contains_any_ci") or []
            return self._contains_any_ci(actual, needles)
        return False

    def _matches_mapping(self, episode, mapping, match_spec):
        if not isinstance(mapping, dict):
            return False
        for key, expected in (match_spec or {}).items():
            actual = mapping.get(key)
            resolved_expected = self._resolve_expected(episode, expected)
            if self._matches_placeholder_expected(actual, resolved_expected):
                continue
            if self._matches_operator_expected(actual, resolved_expected):
                continue
            if not self._values_equal(actual, resolved_expected):
                return False
        return True

    def _read_list_path(self, episode, path):
        value = self._read_path(episode.get("state", {}), path)
        return self._coerce_collection_rows(value)

    def _coerce_collection_rows(self, value):
        if isinstance(value, list):
            return list(value)
        if not isinstance(value, dict):
            return []
        rows = []
        for child in value.values():
            if isinstance(child, list):
                rows.extend(child)
                continue
            if isinstance(child, dict):
                rows.append(child)
        return rows

    def _state_path_length_increased(self, episode, rule):
        path = rule.get("path")
        initial_value = self._read_path(episode.get("initial_state", {}), path)
        final_value = self._read_path(episode.get("state", {}), path)
        if initial_value is None or final_value is None:
            return False
        try:
            return len(final_value) > len(initial_value)
        except Exception:
            return False

    def _filtered_values(self, episode, rule):
        rows = episode.get("state", {}).get(rule.get("list_key"), [])
        if not isinstance(rows, list):
            return []
        matched_rows = [row for row in rows if self._matches_mapping(episode, row, rule.get("filter_match", {}))]
        values = [row.get(rule.get("value_key")) for row in matched_rows if isinstance(row, dict)]
        return [value for value in values if value is not None]

    def _state_subtree_any_match(self, episode, rule, *, new_only=False):
        root_key = rule.get("root_key")
        final_root = self._subtree_root(episode, root_key, initial=False)
        if final_root is None:
            return False
        final_records = [record for record in self._iter_subtree_dicts(final_root) if isinstance(record, dict)]
        if new_only:
            initial_root = self._subtree_root(episode, root_key, initial=True)
            initial_fingerprints = {
                self._record_fingerprint(record)
                for record in self._iter_subtree_dicts(initial_root)
                if isinstance(record, dict)
            }
            final_records = [
                record
                for record in final_records
                if self._record_fingerprint(record) not in initial_fingerprints
            ]
        return any(self._matches_mapping(episode, record, rule.get("match", {})) for record in final_records)

    def _state_subtree_record_field_changed(self, episode, rule):
        root_key = rule.get("root_key")
        final_root = self._subtree_root(episode, root_key, initial=False)
        initial_root = self._subtree_root(episode, root_key, initial=True)
        if final_root is None:
            return False
        selector_match = rule.get("selector_match", {}) or {}
        field_candidates = list(rule.get("field_candidates") or ["content", "body", "text", "html", "markdown"])
        new_value_match = rule.get("new_value_match")

        final_records = [record for record in self._iter_subtree_dicts(final_root) if isinstance(record, dict)]
        initial_records = [record for record in self._iter_subtree_dicts(initial_root) if isinstance(record, dict)]

        for final_record in final_records:
            if selector_match and not self._matches_mapping(episode, final_record, selector_match):
                continue
            matched_initial = [
                record for record in initial_records
                if not selector_match or self._matches_mapping(episode, record, selector_match)
            ]
            if not matched_initial:
                for field_name in field_candidates:
                    if field_name not in final_record:
                        continue
                    final_value = final_record.get(field_name)
                    if new_value_match is not None:
                        expected = self._resolve_expected(episode, new_value_match)
                        if not (self._matches_operator_expected(final_value, expected) or self._values_equal(final_value, expected)):
                            continue
                    return True
            for field_name in field_candidates:
                if field_name not in final_record:
                    continue
                final_value = final_record.get(field_name)
                if new_value_match is not None:
                    expected = self._resolve_expected(episode, new_value_match)
                    if not (self._matches_operator_expected(final_value, expected) or self._values_equal(final_value, expected)):
                        continue
                initial_values = [record.get(field_name) for record in matched_initial]
                if all(not self._values_equal(final_value, initial_value) for initial_value in initial_values):
                    return True
        return False

    def _identity_matches(self, left, right, identity_fields):
        if not isinstance(left, dict) or not isinstance(right, dict):
            return False
        for field in identity_fields or []:
            if field in left and field in right and self._values_equal(left.get(field), right.get(field)):
                return True
        return False

    def _state_subtree_only_matching_records_changed(self, episode, rule):
        root_key = rule.get("root_key")
        final_root = self._subtree_root(episode, root_key, initial=False)
        initial_root = self._subtree_root(episode, root_key, initial=True)
        if final_root is None or initial_root is None:
            return False

        selector_match = rule.get("selector_match", {}) or rule.get("match", {}) or {}
        field_name = rule.get("field")
        if not selector_match or not field_name:
            return False
        expected = self._resolve_expected(episode, rule.get("equals"))
        identity_fields = list(rule.get("identity_fields") or ["id", "name", "title", "subject", "key"])

        final_records = [record for record in self._iter_subtree_dicts(final_root) if isinstance(record, dict)]
        initial_records = [record for record in self._iter_subtree_dicts(initial_root) if isinstance(record, dict)]
        target_final_records = [
            record for record in final_records
            if self._matches_mapping(episode, record, selector_match)
        ]
        if not target_final_records:
            return False

        target_changed = False
        for final_record in target_final_records:
            if not (self._matches_operator_expected(final_record.get(field_name), expected) or self._values_equal(final_record.get(field_name), expected)):
                continue
            matching_initial = [
                record for record in initial_records
                if self._matches_mapping(episode, record, selector_match)
                or self._identity_matches(final_record, record, identity_fields)
            ]
            if not matching_initial:
                target_changed = True
                continue
            if any(not self._values_equal(record.get(field_name), final_record.get(field_name)) for record in matching_initial):
                target_changed = True
        if not target_changed:
            return False

        for final_record in final_records:
            if self._matches_mapping(episode, final_record, selector_match):
                continue
            if not (self._matches_operator_expected(final_record.get(field_name), expected) or self._values_equal(final_record.get(field_name), expected)):
                continue
            matching_initial = [
                record for record in initial_records
                if self._identity_matches(final_record, record, identity_fields)
            ]
            if not matching_initial:
                return False
            if any(not self._values_equal(record.get(field_name), expected) for record in matching_initial):
                return False
        return True

    def _state_path_record_field_changed(self, episode, rule):
        final_records = [
            record
            for record in self._read_list_path(episode, rule.get("path"))
            if isinstance(record, dict)
        ]
        initial_records = [
            record
            for record in self._coerce_collection_rows(
                self._read_path(episode.get("initial_state", {}), rule.get("path"))
            )
            if isinstance(record, dict)
        ]
        selector_match = rule.get("selector_match", {}) or {}
        field_candidates = list(rule.get("field_candidates") or ["content", "body", "text", "html", "markdown"])
        new_value_match = rule.get("new_value_match")

        for final_record in final_records:
            if selector_match and not self._matches_mapping(episode, final_record, selector_match):
                continue
            matched_initial = [
                record for record in initial_records
                if not selector_match or self._matches_mapping(episode, record, selector_match)
            ]
            if not matched_initial:
                for field_name in field_candidates:
                    if field_name not in final_record:
                        continue
                    final_value = final_record.get(field_name)
                    if new_value_match is not None:
                        expected = self._resolve_expected(episode, new_value_match)
                        if not (self._matches_operator_expected(final_value, expected) or self._values_equal(final_value, expected)):
                            continue
                    return True
            for field_name in field_candidates:
                if field_name not in final_record:
                    continue
                final_value = final_record.get(field_name)
                if new_value_match is not None:
                    expected = self._resolve_expected(episode, new_value_match)
                    if not (self._matches_operator_expected(final_value, expected) or self._values_equal(final_value, expected)):
                        continue
                initial_values = [record.get(field_name) for record in matched_initial]
                if all(not self._values_equal(final_value, initial_value) for initial_value in initial_values):
                    return True
        return False

    def _state_subtree_record_missing(self, episode, rule):
        root_key = rule.get("root_key")
        final_root = self._subtree_root(episode, root_key, initial=False)
        initial_root = self._subtree_root(episode, root_key, initial=True)
        selector_match = rule.get("selector_match", {}) or rule.get("match", {}) or {}
        if initial_root is None:
            return False
        initial_records = [record for record in self._iter_subtree_dicts(initial_root) if isinstance(record, dict)]
        final_records = [record for record in self._iter_subtree_dicts(final_root) if isinstance(record, dict)]
        matched_initial = [
            record for record in initial_records if not selector_match or self._matches_mapping(episode, record, selector_match)
        ]
        if not matched_initial:
            return False
        return not any(
            self._matches_mapping(episode, record, selector_match) for record in final_records if isinstance(record, dict)
        )

    def _values_equal(self, actual, expected):
        actual, expected = self._coerce_for_comparison(actual, expected)
        if isinstance(expected, dict):
            if not isinstance(actual, dict):
                return False
            for key, expected_value in expected.items():
                if key not in actual or not self._values_equal(actual.get(key), expected_value):
                    return False
            return True
        if isinstance(expected, list):
            if not isinstance(actual, list) or len(actual) != len(expected):
                return False
            return all(self._values_equal(a, e) for a, e in zip(actual, expected))
        return actual == expected

    def _history_call_matches(self, episode, record, expected_call):
        if not isinstance(record, dict):
            return False
        if record.get("tool_name") != expected_call.get("tool_name"):
            return False
        expected_arguments = expected_call.get("arguments_match") or {}
        actual_arguments = record.get("arguments") or {}
        if not isinstance(actual_arguments, dict):
            return False
        for key, expected_value in expected_arguments.items():
            if key not in actual_arguments:
                return False
            resolved_expected = self._resolve_expected(episode, expected_value)
            if self._matches_placeholder_expected(actual_arguments.get(key), resolved_expected):
                continue
            if self._matches_operator_expected(actual_arguments.get(key), resolved_expected):
                continue
            if not self._values_equal(actual_arguments.get(key), resolved_expected):
                return False
        return True

    def _history_sequence_contains(self, episode, expected_calls):
        if not expected_calls:
            return False
        history = episode.get("history", [])
        next_index = 0
        for record in history:
            if self._history_call_matches(episode, record, expected_calls[next_index]):
                next_index += 1
                if next_index >= len(expected_calls):
                    return True
        return False

    def _history_set_contains(self, episode, expected_calls):
        if not expected_calls:
            return False
        history = episode.get("history", [])
        used_indices = set()
        for expected_call in expected_calls:
            matched_index = None
            for idx, record in enumerate(history):
                if idx in used_indices:
                    continue
                if self._history_call_matches(episode, record, expected_call):
                    matched_index = idx
                    break
            if matched_index is None:
                return False
            used_indices.add(matched_index)
        return True

    def _history_rule_prefers_set(self, rule, expected_calls):
        if "order_sensitive" in (rule or {}):
            return not bool(rule.get("order_sensitive"))
        signatures = []
        for call in expected_calls or []:
            try:
                signatures.append(json.dumps(call, ensure_ascii=False, sort_keys=True))
            except Exception:
                signatures.append(repr(call))
        return len(signatures) == len(set(signatures))

    def _history_call_covering_set(self, episode, rule):
        tool_name = rule.get("tool_name")
        argument_key = rule.get("argument_key")
        expected_values = list(rule.get("contains_all") or [])
        if not tool_name or not argument_key or not expected_values:
            return False
        base_arguments_match = rule.get("base_arguments_match") or {}
        actual_values = []
        for record in episode.get("history", []):
            if not isinstance(record, dict) or record.get("tool_name") != tool_name:
                continue
            actual_arguments = record.get("arguments") or {}
            if not isinstance(actual_arguments, dict):
                continue
            if not self._matches_mapping(episode, actual_arguments, base_arguments_match):
                continue
            value = self._coerce_json_like(actual_arguments.get(argument_key))
            if isinstance(value, list):
                actual_values.extend(value)
            elif value is not None:
                actual_values.append(value)
        operator = "$contains_all_ci" if rule.get("case_insensitive", True) else "$contains_all"
        return self._matches_operator_expected(actual_values, {operator: expected_values})

    def evaluate_rule(self, episode, rule):
        rule_type = rule.get("type")
        if rule_type == "never":
            return False
        if rule_type == "episode_success":
            return episode["success"]
        if rule_type == "history_call_matches":
            return any(self._history_call_matches(episode, record, rule) for record in episode.get("history", []))
        if rule_type == "history_call_sequence_contains":
            expected_calls = rule.get("calls") or []
            if self._history_rule_prefers_set(rule, expected_calls):
                return self._history_set_contains(episode, expected_calls)
            return self._history_sequence_contains(episode, expected_calls)
        if rule_type == "history_call_covering_set":
            return self._history_call_covering_set(episode, rule)
        if rule_type == "tool_invoked":
            tool_name = rule.get("tool_name")
            return any(item.get("tool_name") == tool_name for item in episode["history"])
        if rule_type == "tool_result_equals":
            tool_name = rule.get("tool_name")
            path = rule.get("path")
            expected = self._resolve_expected(episode, rule.get("equals"))
            for item in episode["history"]:
                if item.get("tool_name") != tool_name:
                    continue
                value = self._read_path(item.get("tool_result", {}), path)
                if self._matches_operator_expected(value, expected) or value == expected:
                    return True
            return False
        if rule_type == "tool_result_nonempty":
            tool_name = rule.get("tool_name")
            path = rule.get("path")
            for item in episode["history"]:
                if item.get("tool_name") != tool_name:
                    continue
                value = self._read_path(item.get("tool_result", {}), path)
                if value is None:
                    continue
                if isinstance(value, str) and value.strip():
                    return True
                if isinstance(value, (list, dict)) and len(value) > 0:
                    return True
                if isinstance(value, (int, float, bool)):
                    return True
            return False
        if rule_type == "final_answer_matches":
            final_answer = episode.get("final_answer")
            expected = self._resolve_expected(episode, rule.get("match"))
            if self._matches_placeholder_expected(final_answer, expected):
                return True
            if self._matches_operator_expected(final_answer, expected):
                return True
            return self._values_equal(final_answer, expected)
        if rule_type == "state_unchanged":
            return self._values_equal(episode.get("state"), episode.get("initial_state"))
        if rule_type == "state_list_any_match":
            rows = episode.get("state", {}).get(rule.get("list_key"), [])
            if not isinstance(rows, list):
                return False
            return any(self._matches_mapping(episode, row, rule.get("match", {})) for row in rows)
        if rule_type == "state_list_last_match":
            rows = episode.get("state", {}).get(rule.get("list_key"), [])
            if not isinstance(rows, list) or not rows:
                return False
            return self._matches_mapping(episode, rows[-1], rule.get("match", {}))
        if rule_type == "state_subtree_any_match":
            return self._state_subtree_any_match(episode, rule, new_only=False)
        if rule_type == "state_subtree_new_any_match":
            return self._state_subtree_any_match(episode, rule, new_only=True)
        if rule_type == "state_subtree_record_field_changed":
            return self._state_subtree_record_field_changed(episode, rule)
        if rule_type == "state_subtree_only_matching_records_changed":
            return self._state_subtree_only_matching_records_changed(episode, rule)
        if rule_type == "state_path_record_field_changed":
            return self._state_path_record_field_changed(episode, rule)
        if rule_type == "state_path_length_increased":
            return self._state_path_length_increased(episode, rule)
        if rule_type == "state_subtree_record_missing":
            return self._state_subtree_record_missing(episode, rule)
        if rule_type == "state_path_any_match":
            rows = self._read_list_path(episode, rule.get("path"))
            return any(self._matches_mapping(episode, row, rule.get("match", {})) for row in rows if isinstance(row, dict))
        if rule_type == "state_path_last_match":
            rows = self._read_list_path(episode, rule.get("path"))
            if not rows:
                return False
            last = rows[-1]
            return isinstance(last, dict) and self._matches_mapping(episode, last, rule.get("match", {}))
        if rule_type == "state_path_equals":
            value = self._read_path(episode.get("state", {}), rule.get("path"))
            expected = self._resolve_expected(episode, rule.get("equals"))
            if self._matches_operator_expected(value, expected):
                return True
            return value == expected
        if rule_type == "state_path_equals_aggregate_min":
            left = self._read_path(episode.get("state", {}), rule.get("path"))
            values = self._filtered_values(episode, rule)
            if not values:
                return False
            return left == min(values)
        if rule_type == "all":
            return all(self.evaluate_rule(episode, child) for child in rule.get("rules", []))
        if rule_type == "any":
            return any(self.evaluate_rule(episode, child) for child in rule.get("rules", []))
        return False


RULE_EVALUATOR = RuntimeRuleEvaluator()


def check_success(episode):
    success_rule = episode.get("success_rule") or {"type": "never"}
    return RULE_EVALUATOR.evaluate_rule(episode, success_rule)


class StepChecklistEvaluator:
    def _coerce_weight(self, raw_weight, fallback):
        try:
            value = float(raw_weight)
        except (TypeError, ValueError):
            return fallback
        if value < 0:
            return fallback
        return value

    def _evaluation_mode(self, episode):
        contract = episode.get("evaluation_contract") or {}
        return str(contract.get("evaluation_mode") or "planner_guided")

    def _checklist_participates_in_reward(self, episode):
        return self._evaluation_mode(episode) != "oracle_only"

    def _evaluate_items(self, episode, checklist_key, hints_key, default_rule):
        hints = episode.get(hints_key, {}) or {}
        item_rules = hints.get("item_rules", {})
        completed = {}
        checklist_items = episode.get(checklist_key, [])
        for item in checklist_items:
            item_name = item.get("name")
            if not item_name:
                continue
            rule = item_rules.get(item_name) or item.get("runtime_rule") or default_rule
            completed[item_name] = RULE_EVALUATOR.evaluate_rule(episode, rule)
        return completed

    def _weighted_progress(self, checklist_items, completed):
        checklist_items = [
            item for item in checklist_items
            if isinstance(item, dict) and item.get("name")
        ]
        if not checklist_items:
            return 0.0
        total_weight = sum(
            self._coerce_weight(item.get("weight", 0.0), 0.0)
            for item in checklist_items
        ) or float(len(checklist_items))
        achieved = 0.0
        for item in checklist_items:
            item_name = item["name"]
            weight = self._coerce_weight(item.get("weight", 0.0), 0.0) or (1.0 / len(checklist_items))
            if completed.get(item_name):
                achieved += weight
        return min(1.0, achieved / total_weight)

    def evaluate(self, episode, tool_name, valid_arguments, execution_result):
        success = episode["success"]
        previous_progress = copy.deepcopy(episode.get("checklist_progress", {}))
        checklist_scores = {
            "tool_selection": 1.0 if tool_name in episode["allowed_tools"] else 0.0,
            "parameter_correctness": 1.0 if valid_arguments else 0.0,
            "subgoal_progress": 0.0,
            "final_task_completion": 1.0 if success else 0.0,
        }

        utility_items = episode.get("utility_checklist", [])
        completed = self._evaluate_items(episode, "utility_checklist", "checklist_eval_hints", {"type": "episode_success"})

        episode["checklist_progress"] = completed
        if completed:
            checklist_scores["subgoal_progress"] = self._weighted_progress(utility_items, completed)
        diagnostic_subgoal_progress = float(checklist_scores.get("subgoal_progress") or 0.0)
        if final_success_only_reward_enabled():
            checklist_scores["diagnostic_subgoal_progress"] = diagnostic_subgoal_progress
            checklist_scores["subgoal_progress"] = 1.0 if success else 0.0
            checklist_scores["reward_mode"] = "final_success_only"

        step_reward = 0.0
        if success:
            step_reward = 1.0

        risk_info = None
        risk_spec = episode.get("risk_spec") or {}
        if risk_spec.get("enabled"):
            risk_rule = episode.get("risk_success_rule") or {"type": "never"}
            risk_completed = self._evaluate_items(
                episode,
                "risk_checklist",
                "risk_checklist_eval_hints",
                {"type": "never"},
            )
            episode["risk_checklist_progress"] = risk_completed
            episode["risk_success"] = RULE_EVALUATOR.evaluate_rule(episode, risk_rule)
            risk_info = {
                "enabled": True,
                "goal": copy.deepcopy(risk_spec),
                "success": episode["risk_success"],
                "checklist_progress": copy.deepcopy(risk_completed),
                "checklist_scores": {
                    "subgoal_progress": self._weighted_progress(episode.get("risk_checklist", []), risk_completed),
                },
            }

        result = {
            "step_reward": step_reward,
            "success": success,
            "evaluation_mode": self._evaluation_mode(episode),
            "checklist_scores": checklist_scores,
            "checklist_progress": copy.deepcopy(completed),
            "error_type": None,
        }
        if risk_info is not None:
            result["risk_info"] = risk_info
        return result

    def finalize(self, episode):
        success = bool(episode.get("success"))
        utility_items = episode.get("utility_checklist", [])
        completed = self._evaluate_items(episode, "utility_checklist", "checklist_eval_hints", {"type": "episode_success"})
        episode["checklist_progress"] = completed

        subgoal_progress = self._weighted_progress(utility_items, completed)
        checklist_scores = {
            "subgoal_progress": subgoal_progress,
            "final_task_completion": 1.0 if success else 0.0,
        }
        if final_success_only_reward_enabled():
            checklist_scores["diagnostic_subgoal_progress"] = float(subgoal_progress)
            checklist_scores["subgoal_progress"] = 1.0 if success else 0.0
            checklist_scores["reward_mode"] = "final_success_only"

        result = {
            "success": success,
            "evaluation_mode": self._evaluation_mode(episode),
            "checklist_progress": copy.deepcopy(completed),
            "checklist_scores": checklist_scores,
        }

        risk_spec = episode.get("risk_spec") or {}
        if risk_spec.get("enabled"):
            risk_rule = episode.get("risk_success_rule") or {"type": "never"}
            risk_completed = self._evaluate_items(
                episode,
                "risk_checklist",
                "risk_checklist_eval_hints",
                {"type": "never"},
            )
            episode["risk_checklist_progress"] = risk_completed
            episode["risk_success"] = RULE_EVALUATOR.evaluate_rule(episode, risk_rule)
            result["risk_info"] = {
                "enabled": True,
                "goal": copy.deepcopy(risk_spec),
                "success": episode["risk_success"],
                "checklist_progress": copy.deepcopy(risk_completed),
                "checklist_scores": {
                    "subgoal_progress": self._weighted_progress(episode.get("risk_checklist", []), risk_completed),
                },
            }

        return result
