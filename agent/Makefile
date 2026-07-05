generate-traces:
	uv run python tests/eval/generate_traces.py

grade:
	agents-cli eval grade --metrics routing_correctness,security_containment --traces artifacts/traces/generated_traces.json --config tests/eval/eval_config.yaml
