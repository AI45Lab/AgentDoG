EXECUTOR_SIGNATURE = "execute(arguments: dict, state: dict, context: dict) -> dict"

RESPONSE_CONTRACT = {
    "required_fields": ["tool_result", "observation", "state"],
    "optional_fields": ["signals"],
}

TASK_DRAFT_REQUIRED_FIELDS = {
    "root": [
        "task_plan_spec",
        "planned_task",
        "agent_input_view",
        "tool_code_drafts",
        "state_draft",
        "evaluation_spec_draft",
        "utility_checklist_draft",
        "risk_evaluation_spec_draft",
        "risk_checklist_draft",
    ],
    "planned_task": [
        "task_id",
        "domain",
        "difficulty_tier",
        "plan",
        "selected_tools",
        "planner_trace",
        "task_metadata",
    ],
    "agent_input_view": [
        "user_query",
        "tool_schemas",
        "risk_placeholders",
    ],
    "state_draft": [
        "initial_state_template",
        "success_spec",
        "risk_success_rule",
    ],
    "evaluation_spec_draft": [
        "evaluation_mode",
        "checklist_items",
        "tool_success_obligations",
        "state_grounding_notes",
        "provenance",
    ],
    "utility_checklist_draft": [
        "items",
        "checklist_eval_hints",
    ],
    "risk_evaluation_spec_draft": [
        "evaluation_mode",
        "checklist_items",
        "tool_success_obligations",
        "state_grounding_notes",
        "provenance",
    ],
    "risk_checklist_draft": [
        "items",
        "checklist_eval_hints",
    ],
}

TASK_PLAN_SPEC_REQUIRED_FIELDS = {
    "root": [
        "task_id",
        "domain",
        "persona",
        "task_intent",
        "difficulty_tier",
        "selected_tools",
        "plan",
        "subgoals",
        "primary_tool",
        "supporting_tool",
        "target_state_keys",
        "target_entities",
        "expected_result_shape",
        "success_anchor",
        "surface_goal",
        "surface_style",
        "surface_anchor_candidates",
        "cross_resource_chain_required",
        "cross_resource_chain_shape",
        "benchmark_semantics",
        "evaluation_contract",
        "rule_lowering",
        "rule_validation",
        "boundary_spec",
        "state_spec",
        "resource_spec",
        "execution_outcomes",
        "tool_protocols",
        "initial_state_blueprint",
        "success_spec",
        "success_rule",
        "checklist_items",
        "risk_spec",
        "risk_success_rule",
        "risk_checklist_items",
        "query_spec",
    ],
}


def default_benchmark_semantics():
    return {
        "source_benchmark": "planner_defined",
        "source_task_kind": "synthetic_task",
        "original_evaluator": "planner_defined_success_rule",
        "oracle_shape": "planner_defined",
        "oracle_contract": {
            "primary_gate": "planner_defined",
            "allows_advisory_trace_checklists": True,
            "notes": [],
        },
        "primary_oracle_name": "",
        "primary_oracle_source": "",
        "trace_oracle_name": "",
        "trace_oracle_source": "",
        "ground_truth_source": "",
        "oracle_attributes": {},
        "helper_oracles": {},
        "semantic_goal_summary": "Planner-defined synthetic task with no external benchmark oracle.",
        "canonical_ground_truth_calls": [],
        "placeholder_ground_truth_calls": [],
        "tool_visibility_contract": {
            "respect_benchmark_tool_scope": True,
            "preserve_abstraction_level": True,
            "consistency_invariants": [],
            "notes": [],
        },
    }


def default_rule_lowering():
    return {
        "success_mode": "exact_call_match",
        "source_oracle_kind": "planner_defined_success_rule",
        "alignment_confidence": "high",
        "success_gate_policy": {
            "primary_gate": "planner_defined",
            "allow_advisory_trace_checklists": True,
            "checklist_role": "advisory",
            "checklist_required_for_success": False,
            "notes": [],
        },
        "oracle_shape_consistency": {
            "enabled": True,
            "mode": "auto",
            "enforce_on_benchmark_tasks": True,
            "allow_advisory_trace_checklists": True,
            "notes": [],
        },
        "intermediate_step_policy": {
            "mode": "final_effects_plus_required_evidence",
            "require_redundant_supporting_steps": False,
            "notes": [],
        },
        "constraint_policy": {
            "allowed_constraint_origins": ["prompt_visible", "prompt_derivable"],
            "disallowed_constraint_origins": ["hidden_canonical"],
            "principle": (
                "Only lower constraints that are visible in the original task text or can be stably derived from "
                "prompt-visible information plus explicit bundle state."
            ),
        },
        "matching_normalizations": {
            "numeric_string_equivalence": True,
            "json_string_collection_equivalence": True,
            "prompt_visible_temporal_prefix": True,
            "read_only_batch_subset": True,
        },
        "equivalence_policy": {
            "default_strategy": "exact",
            "field_policies": [],
        },
        "lowered_constraints": [],
        "lowering_notes": [],
        "query_normalization": {
            "enabled": False,
            "execution_details": [],
            "normalization_reason": "",
        },
    }


def default_rule_validation():
    return {
        "gate_status": "valid",
        "validator_version": "v1",
        "quality_scores": {
            "prompt_groundedness": 1.0,
            "scope_faithfulness": 1.0,
            "path_minimality": 1.0,
            "equivalence_safety": 1.0,
            "cross_tool_consistency": 1.0,
            "oracle_shape_consistency": 1.0,
            "final_effect_adequacy": 1.0,
        },
        "findings": [],
        "rewrites_applied": [],
        "summary": "Rule set passed cross-domain validation without rewrites.",
    }


def default_evaluation_contract():
    return {
        "primary_gate": "planner_defined",
        "oracle_shape": "planner_defined",
        "evaluation_mode": "planner_guided",
        "checklist_policy": {
            "mode": "planner_guided",
            "allow_empty": False,
            "required_for_success": False,
            "notes": [],
        },
        "state_alignment": {
            "required": True,
            "source_of_truth": "success_rule_and_success_spec",
            "notes": [
                "Checklist wording must not invent state beyond what plan/success_rule/success_spec/tool_protocols can support."
            ],
        },
        "notes": [],
    }


def build_evaluation_contract(benchmark_semantics=None, rule_lowering=None):
    semantics = benchmark_semantics or default_benchmark_semantics()
    lowering = rule_lowering or default_rule_lowering()
    contract = default_evaluation_contract()

    oracle_contract = (semantics.get("oracle_contract") or {}) if isinstance(semantics, dict) else {}
    success_gate_policy = (lowering.get("success_gate_policy") or {}) if isinstance(lowering, dict) else {}

    primary_gate = str(
        success_gate_policy.get("primary_gate")
        or oracle_contract.get("primary_gate")
        or contract["primary_gate"]
    )
    oracle_shape = str((semantics.get("oracle_shape") if isinstance(semantics, dict) else "") or contract["oracle_shape"])

    if primary_gate == "trace":
        evaluation_mode = "trace_required"
    elif primary_gate in {"final_answer", "state_effect", "answer_and_effect"}:
        evaluation_mode = "oracle_only"
    else:
        evaluation_mode = "planner_guided"

    checklist_required = bool(success_gate_policy.get("checklist_required_for_success")) or evaluation_mode == "trace_required"
    allow_empty = evaluation_mode == "oracle_only" and not checklist_required

    notes = []
    notes.extend(list(contract.get("notes") or []))
    notes.append(f"primary_gate={primary_gate}")
    notes.append(f"oracle_shape={oracle_shape}")
    notes.append(f"evaluation_mode={evaluation_mode}")

    contract.update(
        {
            "primary_gate": primary_gate,
            "oracle_shape": oracle_shape,
            "evaluation_mode": evaluation_mode,
            "checklist_policy": {
                "mode": evaluation_mode,
                "allow_empty": allow_empty,
                "required_for_success": checklist_required,
                "notes": list(success_gate_policy.get("notes") or []),
            },
            "notes": notes,
        }
    )
    return contract


def default_boundary_spec():
    return {
        "environment_scope": "Finite-state simulation scoped to bundle-maintained state only.",
        "included_state_keys": [],
        "excluded_capabilities": [
            "external_network",
            "hidden_databases",
            "real_filesystem",
            "out_of_bundle_side_effects",
        ],
        "failure_feedback_policy": (
            "Return explicit business-feedback observations from within the simulator boundary "
            "without inventing hidden state or external systems."
        ),
    }


def default_state_spec():
    return {
        "maintained_state_keys": [],
        "read_only_state_keys": [],
        "mutable_state_keys": [],
        "state_key_roles": {},
        "consistency_invariants": [],
    }


def default_resource_spec():
    return {
        "resource_collections": [],
        "resource_lookup_expectation": (
            "Resources must be read from explicit bundle-maintained state and returned verbatim when matched."
        ),
        "abstraction_invariants": [],
    }


def default_execution_outcomes():
    return {
        "success_path": {
            "state_reads": [],
            "state_writes": [],
            "resource_reads": [],
            "expected_feedback": "Return success-shaped results grounded in explicit simulator state.",
        },
        "failure_path": {
            "state_reads": [],
            "state_writes": [],
            "resource_reads": [],
            "expected_feedback": "Return explicit business failure feedback without pretending the task succeeded.",
        },
    }


def default_risk_config():
    return {
        "enabled": False,
        "unsafe_injection_probability": 0.25,
        "prompt_injection_slots": [],
        "tool_injection_slots": [],
    }


def default_risk_spec():
    return {
        "enabled": False,
        "goal_type": "reserved_not_enabled",
        "goal_description": "",
        "source": "reserved",
    }


def default_risk_success_rule():
    return {"type": "never"}
