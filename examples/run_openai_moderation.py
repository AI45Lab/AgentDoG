import argparse
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Union


def format_conversation_history(example: Any) -> str:
    if isinstance(example, str):
        return example

    if isinstance(example, list):
        return json.dumps(example, ensure_ascii=False, indent=2)

    if not isinstance(example, dict):
        return json.dumps(example, ensure_ascii=False, indent=2)

    contents = example.get("contents")
    if not isinstance(contents, list):
        return json.dumps(example, ensure_ascii=False, indent=2)

    history_parts: List[str] = []

    profile = example.get("profile")
    if isinstance(profile, str) and profile.strip():
        history_parts.append(f"=== Agent Profile ===\n{profile.strip()}\n")

    history_parts.append("=== Conversation History ===")

    for round_idx, round_item in enumerate(contents, 1):
        if not isinstance(round_item, list):
            continue
        for turn in round_item:
            if not isinstance(turn, dict):
                continue
            role = turn.get("role")
            if role == "user":
                content = turn.get("content")
                if content:
                    history_parts.append(f"\n[USER]: {content}")
            elif role == "agent":
                agent_parts: List[str] = []
                for key, value in turn.items():
                    if key == "role" or value in (None, ""):
                        continue
                    agent_parts.append(f"[{key.upper()}]: {str(value).strip()}")
                if agent_parts:
                    history_parts.append("\n[AGENT]:\n" + "\n".join(agent_parts))
            elif role == "environment":
                content = turn.get("content")
                if content:
                    history_parts.append(f"\n[ENVIRONMENT]: {content}")
            else:
                history_parts.append(f"\n[{str(role).upper()}]: {json.dumps(turn, ensure_ascii=False)}")

    return "\n".join(history_parts)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8000/v1")
    parser.add_argument("--api-key", default="EMPTY")
    parser.add_argument("--model", required=True)
    parser.add_argument("--trajectory", required=True, help="Path to a trajectory JSON file.")
    parser.add_argument("--prompt", default="prompts/trajectory_binary.txt", help="Prompt template path.")
    parser.add_argument("--taxonomy", default=None, help="Optional taxonomy file (used by fine-grained prompt).")
    args = parser.parse_args()

    from openai import OpenAI

    trajectory_obj = json.loads(Path(args.trajectory).read_text(encoding="utf-8"))
    trajectory_text = format_conversation_history(trajectory_obj)

    prompt_template = Path(args.prompt).read_text(encoding="utf-8")
    taxonomy_text = ""
    if args.taxonomy:
        taxonomy_text = Path(args.taxonomy).read_text(encoding="utf-8")

    prompt = prompt_template.format(trajectory=trajectory_text, taxonomy=taxonomy_text)

    client = OpenAI(api_key=args.api_key, base_url=args.base_url)
    resp = client.chat.completions.create(model=args.model, messages=[{"role": "user", "content": prompt}])
    print(resp.choices[0].message.content)


if __name__ == "__main__":
    main()

