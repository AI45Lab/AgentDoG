import copy


ALLOWED_PROVENANCE_SOURCES = (
    "plan",
    "success_rule",
    "success_spec",
    "state_spec",
    "tool_protocols",
    "benchmark_semantics",
    "rule_lowering",
)


def _unique_list(values):
    seen = set()
    ordered = []
    for value in values or []:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        ordered.append(text)
    return ordered


def normalize_provenance_list(provenance, fallback=None):
    allowed = set(ALLOWED_PROVENANCE_SOURCES)
    normalized = []
    seen = set()
    for item in provenance or []:
        text = str(item or "").strip()
        if not text:
            continue
        if text not in allowed:
            raise ValueError(f"Unsupported provenance source: {text}")
        if text in seen:
            continue
        seen.add(text)
        normalized.append(text)
    if normalized:
        return normalized
    fallback_values = [item for item in (fallback or []) if str(item or "").strip() in allowed]
    return _unique_list(fallback_values)


def _validate_match_mapping(mapping):
    if mapping is None:
        return
    if not isinstance(mapping, dict):
        raise ValueError("rule match/filter_match must be a dict.")


def _validate_runtime_rule(rule):
    if not isinstance(rule, dict):
        raise ValueError("runtime_rule must be a dict.")
    rule_type = rule.get("type")
    if rule_type in {"never", "episode_success"}:
        return
    if rule_type == "history_call_matches":
        if not rule.get("tool_name"):
            raise ValueError("history_call_matches runtime_rule requires tool_name.")
        _validate_match_mapping(rule.get("arguments_match"))
        return
    if rule_type == "history_call_covering_set":
        if not rule.get("tool_name"):
            raise ValueError("history_call_covering_set runtime_rule requires tool_name.")
        if not rule.get("argument_key"):
            raise ValueError("history_call_covering_set runtime_rule requires argument_key.")
        if not isinstance(rule.get("contains_all"), list) or not rule.get("contains_all"):
            raise ValueError("history_call_covering_set runtime_rule requires non-empty contains_all.")
        _validate_match_mapping(rule.get("base_arguments_match"))
        return
    if rule_type == "history_call_sequence_contains":
        calls = rule.get("calls")
        if not isinstance(calls, list) or not calls:
            raise ValueError("history_call_sequence_contains runtime_rule requires non-empty calls.")
        for call in calls:
            if not isinstance(call, dict):
                raise ValueError("history_call_sequence_contains calls must be dicts.")
            if not call.get("tool_name"):
                raise ValueError("history_call_sequence_contains call requires tool_name.")
            _validate_match_mapping(call.get("arguments_match"))
        return
    if rule_type == "tool_invoked":
        if not rule.get("tool_name"):
            raise ValueError("tool_invoked runtime_rule requires tool_name.")
        return
    if rule_type == "tool_result_equals":
        if not rule.get("tool_name"):
            raise ValueError("tool_result_equals runtime_rule requires tool_name.")
        if not rule.get("path"):
            raise ValueError("tool_result_equals runtime_rule requires path.")
        if "equals" not in rule:
            raise ValueError("tool_result_equals runtime_rule requires equals.")
        return
    if rule_type == "tool_result_nonempty":
        if not rule.get("tool_name"):
            raise ValueError("tool_result_nonempty runtime_rule requires tool_name.")
        if not rule.get("path"):
            raise ValueError("tool_result_nonempty runtime_rule requires path.")
        return
    if rule_type in {"state_list_any_match", "state_list_last_match"}:
        if not rule.get("list_key"):
            raise ValueError(f"{rule_type} runtime_rule requires list_key.")
        _validate_match_mapping(rule.get("match"))
        return
    if rule_type in {"state_subtree_any_match", "state_subtree_new_any_match"}:
        if not rule.get("root_key"):
            raise ValueError(f"{rule_type} runtime_rule requires root_key.")
        _validate_match_mapping(rule.get("match"))
        return
    if rule_type == "state_subtree_record_field_changed":
        if not rule.get("root_key"):
            raise ValueError("state_subtree_record_field_changed runtime_rule requires root_key.")
        _validate_match_mapping(rule.get("selector_match"))
        field_candidates = rule.get("field_candidates")
        if field_candidates is not None and (not isinstance(field_candidates, list) or not field_candidates):
            raise ValueError("state_subtree_record_field_changed field_candidates must be a non-empty list when provided.")
        return
    if rule_type == "state_subtree_only_matching_records_changed":
        if not rule.get("root_key"):
            raise ValueError("state_subtree_only_matching_records_changed runtime_rule requires root_key.")
        _validate_match_mapping(rule.get("selector_match") or rule.get("match"))
        if not rule.get("field"):
            raise ValueError("state_subtree_only_matching_records_changed runtime_rule requires field.")
        if "equals" not in rule:
            raise ValueError("state_subtree_only_matching_records_changed runtime_rule requires equals.")
        identity_fields = rule.get("identity_fields")
        if identity_fields is not None and (not isinstance(identity_fields, list) or not identity_fields):
            raise ValueError("state_subtree_only_matching_records_changed identity_fields must be a non-empty list when provided.")
        return
    if rule_type == "state_subtree_record_missing":
        if not rule.get("root_key"):
            raise ValueError("state_subtree_record_missing runtime_rule requires root_key.")
        _validate_match_mapping(rule.get("selector_match") or rule.get("match"))
        return
    if rule_type in {"state_path_any_match", "state_path_last_match"}:
        if not rule.get("path"):
            raise ValueError(f"{rule_type} runtime_rule requires path.")
        _validate_match_mapping(rule.get("match"))
        return
    if rule_type == "state_path_equals":
        if not rule.get("path"):
            raise ValueError("state_path_equals runtime_rule requires path.")
        if "equals" not in rule:
            raise ValueError("state_path_equals runtime_rule requires equals.")
        return
    if rule_type == "state_path_equals_aggregate_min":
        for key in ["path", "list_key", "value_key"]:
            if not rule.get(key):
                raise ValueError(f"state_path_equals_aggregate_min runtime_rule requires {key}.")
        _validate_match_mapping(rule.get("filter_match"))
        return
    if rule_type in {"all", "any"}:
        child_rules = rule.get("rules")
        if not isinstance(child_rules, list) or not child_rules:
            raise ValueError(f"{rule_type} runtime_rule requires non-empty rules.")
        for child in child_rules:
            _validate_runtime_rule(child)
        return
    raise ValueError(f"Unsupported runtime_rule type: {rule_type}")


def normalize_runtime_rule(rule, fallback_rule=None):
    fallback = copy.deepcopy(fallback_rule or {"type": "episode_success"})
    if rule is None:
        return fallback
    try:
        _validate_runtime_rule(rule)
        return copy.deepcopy(rule)
    except Exception:
        return fallback


def build_checklist_eval_hints(success_spec, checklist_items=None):
    checklist_items = checklist_items or []
    item_rules = {}

    for item in checklist_items:
        if not isinstance(item, dict):
            continue
        item_name = item.get("name")
        if not item_name:
            continue
        item_rules[item_name] = normalize_runtime_rule(item.get("runtime_rule"), {"type": "episode_success"})

    return {
        "item_rules": item_rules,
        "progress_mode": "weighted",
    }


def _rule_root_state_keys(rule):
    rule_type = str((rule or {}).get("type") or "")
    keys = []
    if rule_type in {"state_list_any_match", "state_list_last_match"}:
        keys.append(str(rule.get("list_key") or "").strip())
    elif rule_type in {"state_subtree_any_match", "state_subtree_new_any_match", "state_subtree_record_field_changed", "state_subtree_record_missing"}:
        keys.append(str(rule.get("root_key") or "").strip())
    elif rule_type in {"state_path_any_match", "state_path_last_match", "state_path_equals", "state_path_equals_aggregate_min"}:
        path = str(rule.get("path") or "").strip()
        if path:
            keys.append(path.split(".", 1)[0])
    return [key for key in keys if key]


def _rule_mentions_tool(rule, tool_name):
    if not isinstance(rule, dict):
        return False
    rule_type = rule.get("type")
    if rule_type in {"tool_invoked", "tool_result_equals", "history_call_matches"}:
        return rule.get("tool_name") == tool_name
    if rule_type == "history_call_covering_set":
        return rule.get("tool_name") == tool_name
    if rule_type == "history_call_sequence_contains":
        return any(isinstance(call, dict) and call.get("tool_name") == tool_name for call in rule.get("calls", []))
    if rule_type in {"all", "any"}:
        return any(_rule_mentions_tool(child, tool_name) for child in rule.get("rules", []) if isinstance(child, dict))
    return False


def _rule_mentions_state_keys(rule, state_keys):
    if not isinstance(rule, dict):
        return False
    relevant_keys = set(_unique_list(state_keys))
    if not relevant_keys:
        return False
    if relevant_keys.intersection(_rule_root_state_keys(rule)):
        return True
    rule_type = rule.get("type")
    if rule_type in {"all", "any"}:
        return any(_rule_mentions_state_keys(child, relevant_keys) for child in rule.get("rules", []) if isinstance(child, dict))
    return False


def _collect_rule_fragments(rule, tool_name, state_keys, target):
    if not isinstance(rule, dict):
        return
    if _rule_mentions_tool(rule, tool_name) or _rule_mentions_state_keys(rule, state_keys):
        target.append(copy.deepcopy(rule))
        return
    if rule.get("type") in {"all", "any"}:
        for child in rule.get("rules", []):
            if isinstance(child, dict):
                _collect_rule_fragments(child, tool_name, state_keys, target)


def _relevant_rule_fragments_for_tool(tool_name, success_rule, protocol):
    state_access = protocol.get("state_access_plan", {}) or {}
    validation_hints = protocol.get("validation_hints", {}) or {}
    state_keys = _unique_list(
        list(state_access.get("reads_state_keys") or [])
        + list(state_access.get("writes_state_keys") or [])
        + list(validation_hints.get("reads_state_keys") or [])
        + list(validation_hints.get("writes_state_keys") or [])
    )
    collected = []
    _collect_rule_fragments(success_rule or {}, tool_name, state_keys, collected)
    normalized = []
    seen = set()
    for fragment in collected:
        fingerprint = repr(fragment)
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        normalized.append(fragment)
    return normalized


def _success_spec_tool_names(success_spec):
    names = []
    if not isinstance(success_spec, dict):
        return names
    for key in ("primary_tool", "supporting_tool"):
        value = str(success_spec.get(key) or "").strip()
        if value:
            names.append(value)
    for call in success_spec.get("ground_truth_calls") or []:
        if isinstance(call, dict):
            value = str(call.get("tool_name") or "").strip()
            if value:
                names.append(value)
    return _unique_list(names)


def _checklist_mentions_tool(checklist_items, tool_name):
    for item in checklist_items or []:
        if not isinstance(item, dict):
            continue
        if _rule_mentions_tool(item.get("runtime_rule") or {}, tool_name):
            return True
    return False


def _obligation_required_output_fields(protocol, kind):
    required = _unique_list(protocol.get("required_tool_result_keys") or [])
    optional = _unique_list(protocol.get("optional_tool_result_keys") or [])
    output_scope = ((protocol.get("tool_scope") or {}).get("output_scope") or {})
    representation = str(output_scope.get("representation") or "").strip().lower()
    must_preserve_abstraction = bool(output_scope.get("must_preserve_abstraction"))
    if kind == "read_evidence" and not required:
        if must_preserve_abstraction and representation in {"name_list", "field_projection", "raw_content"}:
            return required
        for candidate in ("records", "result", "content"):
            if candidate in optional and candidate not in required:
                required.append(candidate)
                break
    return required


def _tool_failure_behavior(protocol):
    effect_model = protocol.get("effect_model", {}) or {}
    feedback = str(effect_model.get("failure_feedback") or "").strip()
    if feedback:
        return feedback
    return "Return explicit business failure feedback using the same schema and do not claim success."


def _make_obligation(tool_name, kind, protocol, success_rule, provenance):
    state_access = protocol.get("state_access_plan", {}) or {}
    validation_hints = protocol.get("validation_hints", {}) or {}
    must_read_state = _unique_list(
        list(state_access.get("reads_state_keys") or []) + list(validation_hints.get("reads_state_keys") or [])
    )
    must_write_state = _unique_list(
        list(state_access.get("writes_state_keys") or []) + list(validation_hints.get("writes_state_keys") or [])
    )
    rule_fragments = _relevant_rule_fragments_for_tool(tool_name, success_rule, protocol)
    obligation = {
        "tool_name": str(tool_name),
        "kind": str(kind),
        "must_read_state": must_read_state,
        "must_write_state": must_write_state if kind == "write_effect" else [],
        "required_output_fields": _obligation_required_output_fields(protocol, kind),
        "success_link": {
            "summary": (
                "Return evidence needed by downstream actions."
                if kind == "read_evidence"
                else "Produce the tool-local state effect that supports the global success rule."
                if kind == "write_effect"
                else "Expose the benchmark-required trace or tool-call evidence."
            ),
            "rule_fragments": rule_fragments,
        },
        "failure_behavior": _tool_failure_behavior(protocol),
        "provenance": normalize_provenance_list(provenance, fallback=["tool_protocols", "success_rule"]),
    }
    return obligation


def derive_tool_success_obligations(
    selected_tools,
    tool_protocols,
    success_rule,
    success_spec=None,
    state_spec=None,
    evaluation_contract=None,
    checklist_items=None,
):
    obligations = []
    evaluation_mode = str(((evaluation_contract or {}).get("evaluation_mode")) or "")
    success_tool_names = set(_success_spec_tool_names(success_spec))
    for tool_name in selected_tools or []:
        protocol = (tool_protocols or {}).get(tool_name) or {}
        if not isinstance(protocol, dict):
            continue
        state_access = protocol.get("state_access_plan", {}) or {}
        validation_hints = protocol.get("validation_hints", {}) or {}
        writes = _unique_list(
            list(state_access.get("writes_state_keys") or []) + list(validation_hints.get("writes_state_keys") or [])
        )
        reads = _unique_list(
            list(state_access.get("reads_state_keys") or []) + list(validation_hints.get("reads_state_keys") or [])
        )
        has_trace_rule = bool(_relevant_rule_fragments_for_tool(tool_name, success_rule, protocol))
        mentioned_in_checklist = _checklist_mentions_tool(checklist_items, tool_name)
        mentioned_in_success = tool_name in success_tool_names
        if writes:
            obligations.append(
                _make_obligation(
                    tool_name,
                    "write_effect",
                    protocol,
                    success_rule,
                    provenance=["tool_protocols", "success_rule", "success_spec", "state_spec"],
                )
            )
        elif reads and (has_trace_rule or mentioned_in_success or mentioned_in_checklist):
            obligations.append(
                _make_obligation(
                    tool_name,
                    "read_evidence",
                    protocol,
                    success_rule,
                    provenance=["tool_protocols", "state_spec", "success_rule", "success_spec"],
                )
            )
        if has_trace_rule and evaluation_mode == "trace_required":
            obligations.append(
                _make_obligation(
                    tool_name,
                    "trace_evidence",
                    protocol,
                    success_rule,
                    provenance=["success_rule", "benchmark_semantics", "rule_lowering", "tool_protocols"],
                )
            )

    normalized = []
    seen = set()
    for obligation in obligations:
        fingerprint = (
            obligation.get("tool_name"),
            obligation.get("kind"),
            tuple(obligation.get("must_read_state") or []),
            tuple(obligation.get("must_write_state") or []),
        )
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        normalized.append(obligation)
    return normalized


def _default_state_grounding_notes():
    return [
        "Checklist wording and tool obligations must stay grounded in success_rule, success_spec, state_spec, and tool_protocols.",
        "Do not invent hidden state, hidden tools, hidden files, or hidden completion conditions.",
    ]


def build_evaluation_spec_payload(
    *,
    evaluation_contract,
    checklist_items,
    selected_tools,
    tool_protocols,
    success_rule,
    success_spec,
    state_spec,
    benchmark_semantics=None,
    rule_lowering=None,
):
    tool_success_obligations = derive_tool_success_obligations(
        selected_tools,
        tool_protocols,
        success_rule,
        success_spec=success_spec,
        state_spec=state_spec,
        evaluation_contract=evaluation_contract,
        checklist_items=checklist_items,
    )
    normalized_items = []
    provenance_rows = {
        "allowed_sources": list(ALLOWED_PROVENANCE_SOURCES),
        "checklist_items": [],
        "tool_success_obligations": [],
    }
    for item in checklist_items or []:
        normalized_item = copy.deepcopy(item)
        item_provenance = normalize_provenance_list(
            normalized_item.get("provenance"),
            fallback=["plan", "success_rule", "success_spec", "state_spec", "tool_protocols"],
        )
        normalized_item["provenance"] = item_provenance
        normalized_items.append(normalized_item)
        provenance_rows["checklist_items"].append(
            {"name": normalized_item.get("name"), "sources": item_provenance}
        )
    for obligation in tool_success_obligations:
        provenance_rows["tool_success_obligations"].append(
            {
                "tool_name": obligation.get("tool_name"),
                "kind": obligation.get("kind"),
                "sources": list(obligation.get("provenance") or []),
            }
        )
    return {
        "evaluation_mode": str((evaluation_contract or {}).get("evaluation_mode") or "planner_guided"),
        "checklist_items": normalized_items,
        "tool_success_obligations": tool_success_obligations,
        "state_grounding_notes": _default_state_grounding_notes(),
        "provenance": provenance_rows,
    }


def normalize_tool_success_obligations(obligations, selected_tools, tool_protocols, success_rule, evaluation_contract):
    if not isinstance(obligations, list):
        obligations = []
    normalized = []
    allowed_tools = {str(name) for name in (selected_tools or [])}
    for obligation in obligations:
        if not isinstance(obligation, dict):
            continue
        tool_name = str(obligation.get("tool_name") or "").strip()
        kind = str(obligation.get("kind") or "").strip()
        if not tool_name or tool_name not in allowed_tools:
            continue
        if kind not in {"read_evidence", "write_effect", "trace_evidence"}:
            continue
        success_link = obligation.get("success_link") or {}
        if not isinstance(success_link, dict):
            success_link = {}
        normalized.append(
            {
                "tool_name": tool_name,
                "kind": kind,
                "must_read_state": _unique_list(obligation.get("must_read_state") or []),
                "must_write_state": _unique_list(obligation.get("must_write_state") or []),
                "required_output_fields": _unique_list(obligation.get("required_output_fields") or []),
                "success_link": {
                    "summary": str(success_link.get("summary") or "").strip(),
                    "rule_fragments": [
                        normalize_runtime_rule(rule, {"type": "never"})
                        for rule in (success_link.get("rule_fragments") or [])
                        if isinstance(rule, dict)
                    ],
                },
                "failure_behavior": str(obligation.get("failure_behavior") or "").strip(),
                "provenance": normalize_provenance_list(
                    obligation.get("provenance"),
                    fallback=["tool_protocols", "success_rule"],
                ),
            }
        )
    if normalized:
        return normalized
    return derive_tool_success_obligations(
        selected_tools,
        tool_protocols,
        success_rule,
        evaluation_contract=evaluation_contract,
    )


def describe_tool_success_obligations(tool_name, obligations):
    described = []
    for obligation in obligations or []:
        if not isinstance(obligation, dict):
            continue
        if str(obligation.get("tool_name") or "") != str(tool_name):
            continue
        described.append(copy.deepcopy(obligation))
    return described


def _collect_tool_rule_constraints(rule, tool_name, target):
    rule_type = rule.get("type")
    if rule_type in {"tool_invoked", "tool_result_equals", "history_call_matches"} and rule.get("tool_name") == tool_name:
        target.append(copy.deepcopy(rule))
        return
    if rule_type == "history_call_sequence_contains":
        for call in rule.get("calls", []):
            if isinstance(call, dict) and call.get("tool_name") == tool_name:
                target.append({
                    "type": "history_call_matches",
                    "tool_name": tool_name,
                    "arguments_match": copy.deepcopy(call.get("arguments_match") or {}),
                })
        return
    if rule_type in {"all", "any"}:
        for child in rule.get("rules", []):
            if isinstance(child, dict):
                _collect_tool_rule_constraints(child, tool_name, target)


def describe_tool_rule_constraints(tool_name, checklist_items, success_spec):
    hints = build_checklist_eval_hints(success_spec, checklist_items)
    constraints = []
    for item_name, rule in hints.get("item_rules", {}).items():
        item_constraints = []
        _collect_tool_rule_constraints(rule, tool_name, item_constraints)
        if item_constraints:
            constraints.append({
                "checklist_item": item_name,
                "rules": item_constraints,
            })
    return constraints


def build_success_eval_rule(success_spec):
    return normalize_runtime_rule(success_spec.get("success_eval_rule"), {"type": "never"})
