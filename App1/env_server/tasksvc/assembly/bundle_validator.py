from tasksvc.common.contracts import (
    RESPONSE_CONTRACT,
    TASK_DRAFT_REQUIRED_FIELDS,
    TASK_PLAN_SPEC_REQUIRED_FIELDS,
    default_risk_success_rule,
)
from tasksvc.rules.evaluation_hints import (
    ALLOWED_PROVENANCE_SOURCES,
    build_success_eval_rule,
    normalize_runtime_rule,
)
from tasksvc.runtime.tool_runtime import validate_tool_source


def _require(mapping, key, label):
    if key not in mapping:
        raise ValueError(f"Missing required field {label}.{key}")
    return mapping[key]


def _allow_empty_utility_checklist(task_plan_spec):
    evaluation_contract = task_plan_spec.get("evaluation_contract") or {}
    checklist_policy = evaluation_contract.get("checklist_policy") or {}
    return bool(checklist_policy.get("allow_empty"))


def validate_runtime_bundle(bundle):
    task_spec = _require(bundle, "task_spec", "bundle")
    tool_registry_view = _require(bundle, "tool_registry_view", "bundle")
    execution_bundle = _require(bundle, "execution_bundle", "bundle")
    response_contract = _require(bundle, "response_contract", "bundle")
    server_adapter_manifest = _require(bundle, "server_adapter_manifest", "bundle")

    for key in ["task_id", "domain", "user_query", "selected_tools", "risk_spec", "evaluation_contract"]:
        _require(task_spec, key, "task_spec")
    for key in ["tool_schemas", "allowed_tool_names"]:
        _require(tool_registry_view, key, "tool_registry_view")
    for key in ["tool_impl_sources", "tool_entrypoints", "initial_state_template", "success_spec"]:
        _require(execution_bundle, key, "execution_bundle")
    for key in ["required_fields"]:
        _require(response_contract, key, "response_contract")
    for key in ["tool_dispatch_table", "success_eval_type", "checklist_eval_type"]:
        _require(server_adapter_manifest, key, "server_adapter_manifest")

    if not isinstance(execution_bundle["initial_state_template"], dict):
        raise ValueError("execution_bundle.initial_state_template must be a dict.")
    if "scenarios" in execution_bundle and not isinstance(execution_bundle["scenarios"], dict):
        raise ValueError("execution_bundle.scenarios must be a dict when provided.")
    if not isinstance(execution_bundle["success_spec"], dict):
        raise ValueError("execution_bundle.success_spec must be a dict.")
    if not isinstance(task_spec["evaluation_contract"], dict):
        raise ValueError("task_spec.evaluation_contract must be a dict.")

    required_fields = response_contract["required_fields"]
    for field in RESPONSE_CONTRACT["required_fields"]:
        if field not in required_fields:
            raise ValueError(f"response_contract.required_fields must include {field}.")

    dispatch_table = server_adapter_manifest["tool_dispatch_table"]
    for tool_name in tool_registry_view["allowed_tool_names"]:
        if tool_name not in dispatch_table:
            raise ValueError(f"Dispatch table missing allowed tool {tool_name}.")
        dispatch = dispatch_table[tool_name]
        source_key = _require(dispatch, "source_key", f"dispatch[{tool_name}]")
        entrypoint = _require(dispatch, "entrypoint", f"dispatch[{tool_name}]")
        if source_key not in execution_bundle["tool_impl_sources"]:
            raise ValueError(f"Tool source missing for dispatch source key {source_key}.")
        validate_tool_source(execution_bundle["tool_impl_sources"][source_key], entrypoint_name=entrypoint)

    evaluation_bundle = _require(bundle, "evaluation_bundle", "bundle")
    for key in ["utility_evaluation_spec", "risk_evaluation_spec"]:
        _require(evaluation_bundle, key, "evaluation_bundle")
    success_eval_rule = evaluation_bundle.get("success_eval_rule")
    if success_eval_rule is None:
        success_eval_rule = build_success_eval_rule(execution_bundle["success_spec"])
    normalize_runtime_rule(success_eval_rule, {"type": "never"})
    normalize_runtime_rule(
        evaluation_bundle.get("risk_success_eval_rule"),
        default_risk_success_rule(),
    )
    for key in ["risk_checklist", "risk_checklist_eval_hints"]:
        _require(evaluation_bundle, key, "evaluation_bundle")

    return True


def validate_task_draft(task_draft):
    for key in TASK_DRAFT_REQUIRED_FIELDS["root"]:
        _require(task_draft, key, "task_draft")

    task_plan_spec = task_draft["task_plan_spec"]
    planned_task = task_draft["planned_task"]
    agent_input_view = task_draft["agent_input_view"]
    state_draft = task_draft["state_draft"]
    utility_checklist_draft = task_draft["utility_checklist_draft"]
    evaluation_spec_draft = task_draft["evaluation_spec_draft"]
    risk_checklist_draft = task_draft["risk_checklist_draft"]
    risk_evaluation_spec_draft = task_draft["risk_evaluation_spec_draft"]

    for key in TASK_PLAN_SPEC_REQUIRED_FIELDS["root"]:
        _require(task_plan_spec, key, "task_plan_spec")
    for key in TASK_DRAFT_REQUIRED_FIELDS["planned_task"]:
        _require(planned_task, key, "planned_task")
    for key in TASK_DRAFT_REQUIRED_FIELDS["agent_input_view"]:
        _require(agent_input_view, key, "agent_input_view")
    for key in TASK_DRAFT_REQUIRED_FIELDS["state_draft"]:
        _require(state_draft, key, "state_draft")
    for key in TASK_DRAFT_REQUIRED_FIELDS["evaluation_spec_draft"]:
        _require(evaluation_spec_draft, key, "evaluation_spec_draft")
    for key in TASK_DRAFT_REQUIRED_FIELDS["utility_checklist_draft"]:
        _require(utility_checklist_draft, key, "utility_checklist_draft")
    for key in TASK_DRAFT_REQUIRED_FIELDS["risk_evaluation_spec_draft"]:
        _require(risk_evaluation_spec_draft, key, "risk_evaluation_spec_draft")
    for key in TASK_DRAFT_REQUIRED_FIELDS["risk_checklist_draft"]:
        _require(risk_checklist_draft, key, "risk_checklist_draft")

    if not isinstance(planned_task["selected_tools"], list) or not planned_task["selected_tools"]:
        raise ValueError("planned_task.selected_tools must be a non-empty list.")
    if not isinstance(task_plan_spec["selected_tools"], list) or not task_plan_spec["selected_tools"]:
        raise ValueError("task_plan_spec.selected_tools must be a non-empty list.")
    if not isinstance(task_plan_spec["tool_protocols"], dict) or not task_plan_spec["tool_protocols"]:
        raise ValueError("task_plan_spec.tool_protocols must be a non-empty dict.")
    for key in ["boundary_spec", "state_spec", "resource_spec", "execution_outcomes"]:
        if not isinstance(task_plan_spec[key], dict):
            raise ValueError(f"task_plan_spec.{key} must be a dict.")
    if not isinstance(task_plan_spec.get("evaluation_contract"), dict):
        raise ValueError("task_plan_spec.evaluation_contract must be a dict.")
    if not isinstance(task_plan_spec["initial_state_blueprint"], dict):
        raise ValueError("task_plan_spec.initial_state_blueprint must be a dict.")
    if not isinstance(task_plan_spec["success_rule"], dict):
        raise ValueError("task_plan_spec.success_rule must be a dict.")
    if not isinstance(task_plan_spec.get("rule_validation"), dict):
        raise ValueError("task_plan_spec.rule_validation must be a dict.")
    if task_plan_spec["rule_validation"].get("gate_status") == "rejected":
        raise ValueError("task_plan_spec.rule_validation.gate_status must not be rejected.")
    if not isinstance(task_plan_spec["risk_spec"], dict):
        raise ValueError("task_plan_spec.risk_spec must be a dict.")
    if not isinstance(task_plan_spec["risk_success_rule"], dict):
        raise ValueError("task_plan_spec.risk_success_rule must be a dict.")
    if "scenarios" in task_plan_spec and not isinstance(task_plan_spec["scenarios"], dict):
        raise ValueError("task_plan_spec.scenarios must be a dict when provided.")
    if not isinstance(task_plan_spec["checklist_items"], list):
        raise ValueError("task_plan_spec.checklist_items must be a list.")
    if not task_plan_spec["checklist_items"] and not _allow_empty_utility_checklist(task_plan_spec):
        raise ValueError("task_plan_spec.checklist_items must be non-empty unless evaluation_contract allows oracle-only empty checklists.")
    if not isinstance(task_plan_spec["risk_checklist_items"], list):
        raise ValueError("task_plan_spec.risk_checklist_items must be a list.")
    if not isinstance(agent_input_view["tool_schemas"], list) or not agent_input_view["tool_schemas"]:
        raise ValueError("agent_input_view.tool_schemas must be a non-empty list.")
    if "scenarios" in agent_input_view and not isinstance(agent_input_view["scenarios"], dict):
        raise ValueError("agent_input_view.scenarios must be a dict when provided.")
    if not isinstance(task_draft["tool_code_drafts"], dict) or not task_draft["tool_code_drafts"]:
        raise ValueError("tool_code_drafts must be a non-empty dict.")
    if not isinstance(state_draft["initial_state_template"], dict):
        raise ValueError("state_draft.initial_state_template must be a dict.")
    if "scenarios" in state_draft and not isinstance(state_draft["scenarios"], dict):
        raise ValueError("state_draft.scenarios must be a dict when provided.")
    if not isinstance(state_draft["success_spec"], dict):
        raise ValueError("state_draft.success_spec must be a dict.")
    success_rule = state_draft.get("success_rule")
    if success_rule is None:
        success_rule = build_success_eval_rule(state_draft["success_spec"])
    normalize_runtime_rule(success_rule, {"type": "never"})
    normalize_runtime_rule(state_draft.get("risk_success_rule"), default_risk_success_rule())
    if not isinstance(utility_checklist_draft["items"], list):
        raise ValueError("utility_checklist_draft.items must be a list.")
    if not utility_checklist_draft["items"] and not _allow_empty_utility_checklist(task_plan_spec):
        raise ValueError("utility_checklist_draft.items must be non-empty unless evaluation_contract allows oracle-only empty checklists.")
    if not isinstance(risk_checklist_draft["items"], list):
        raise ValueError("risk_checklist_draft.items must be a list.")
    if task_plan_spec["risk_spec"].get("enabled") and not risk_checklist_draft["items"]:
        raise ValueError("risk_checklist_draft.items must be non-empty when risk is enabled.")
    if utility_checklist_draft["items"] != evaluation_spec_draft.get("checklist_items", []):
        raise ValueError("utility_checklist_draft.items must stay aligned with evaluation_spec_draft.checklist_items.")
    if risk_checklist_draft["items"] != risk_evaluation_spec_draft.get("checklist_items", []):
        raise ValueError("risk_checklist_draft.items must stay aligned with risk_evaluation_spec_draft.checklist_items.")
    _validate_evaluation_spec_draft(
        evaluation_spec_draft,
        task_plan_spec,
        label="evaluation_spec_draft",
    )
    _validate_evaluation_spec_draft(
        risk_evaluation_spec_draft,
        task_plan_spec,
        label="risk_evaluation_spec_draft",
    )

    for tool_name in planned_task["selected_tools"]:
        if tool_name not in task_draft["tool_code_drafts"]:
            raise ValueError(f"tool_code_drafts missing selected tool {tool_name}.")
        protocol = task_plan_spec["tool_protocols"].get(tool_name)
        if not isinstance(protocol, dict):
            raise ValueError(f"tool_protocols missing protocol for selected tool {tool_name}.")
        if not isinstance(protocol.get("state_access_plan"), dict):
            raise ValueError(f"tool_protocols[{tool_name}].state_access_plan must be a dict.")
        if not isinstance(protocol.get("effect_model"), dict):
            raise ValueError(f"tool_protocols[{tool_name}].effect_model must be a dict.")

    return True


def _validate_evaluation_spec_draft(spec, task_plan_spec, label):
    if not isinstance(spec, dict):
        raise ValueError(f"{label} must be a dict.")
    if not isinstance(spec.get("checklist_items"), list):
        raise ValueError(f"{label}.checklist_items must be a list.")
    if not isinstance(spec.get("tool_success_obligations"), list):
        raise ValueError(f"{label}.tool_success_obligations must be a list.")
    if not isinstance(spec.get("state_grounding_notes"), list):
        raise ValueError(f"{label}.state_grounding_notes must be a list.")
    if not isinstance(spec.get("provenance"), dict):
        raise ValueError(f"{label}.provenance must be a dict.")
    allowed_sources = set(ALLOWED_PROVENANCE_SOURCES)
    for item in spec.get("checklist_items", []):
        if not isinstance(item, dict):
            raise ValueError(f"{label}.checklist_items entries must be dicts.")
        if not isinstance(item.get("provenance", []), list):
            raise ValueError(f"{label}.checklist_items provenance must be a list.")
        invalid = [source for source in item.get("provenance", []) if source not in allowed_sources]
        if invalid:
            raise ValueError(f"{label}.checklist_items contains invalid provenance sources: {invalid}")
    selected_tools = {str(name) for name in (task_plan_spec.get("selected_tools") or [])}
    for obligation in spec.get("tool_success_obligations", []):
        if not isinstance(obligation, dict):
            raise ValueError(f"{label}.tool_success_obligations entries must be dicts.")
        tool_name = str(obligation.get("tool_name") or "").strip()
        if not tool_name or tool_name not in selected_tools:
            raise ValueError(f"{label}.tool_success_obligations has unknown tool_name: {tool_name}")
        if obligation.get("kind") not in {"read_evidence", "write_effect", "trace_evidence"}:
            raise ValueError(f"{label}.tool_success_obligations has invalid kind: {obligation.get('kind')}")
        invalid = [source for source in obligation.get("provenance", []) if source not in allowed_sources]
        if invalid:
            raise ValueError(f"{label}.tool_success_obligations contains invalid provenance sources: {invalid}")
