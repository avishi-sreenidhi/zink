from pathlib import Path
from zink.config.parser import load_yaml, ConfigError
from zink.schemas import AgentConfig, DeniedEntry
from zink.layers.condition_parser import parse_condition

VALID_TRUST_LEVELS = {"low", "medium", "high"}
VALID_ON_UNKNOWNS  = {"block", "allow", "flag"}

def load_agent_config(path: str | Path, _seen=None, _depth=0) -> AgentConfig:

    if _seen is None:
        _seen = set()

    resolved = Path(path).resolve()

    if resolved in _seen:
        raise ConfigError(f"Circular extends detected: {resolved}")
    
    if _depth > 5:
        raise ConfigError("Extends chain too deep — max depth is 5")
    
    _seen.add(resolved)

    raw = load_yaml(path)

    if "policies" in raw and raw["policies"]:
        parsed_policies = []
        for policy in raw["policies"]:
            if isinstance(policy, dict) and isinstance(policy.get("when"), str):
                policy = {**policy, "when": parse_condition(policy["when"])}
            parsed_policies.append(policy)
        raw["policies"] = tuple(parsed_policies)

    agent_cfg = AgentConfig(**raw)

    if agent_cfg.extends:
        parent_path = (Path(path).parent/agent_cfg.extends).resolve()
        parent_cfg = load_agent_config(parent_path, _seen = _seen, _depth = _depth+1)
        return _merge_agent_configs(parent_cfg,agent_cfg)
    
    return agent_cfg

def _merge_agent_configs(parent: AgentConfig, child: AgentConfig) -> AgentConfig:
    # denied — union
    # policies — union, check final
    # scope — child only
    # everything else — child wins or parent fills
    seen_denied = {(e.action, e.resource) for e in parent.denied}
    merged_denied = list(parent.denied)
    for entry in child.denied:
        key = (entry.action, entry.resource)
        if key not in merged_denied:
            merged_denied.append(entry)
            seen_denied.add(key)

    merged_policies = ()

    return AgentConfig(
        agent = child.agent,
        role = child.role or parent.role,
        trust_level    = child.trust_level or parent.trust_level,
        default_layers = child.default_layers if child.default_layers else parent.default_layers,
        scope = child.scope,
        denied = merged_denied,
        policies = merged_policies,
        injection_patterns = child.injection_patterns if child.injection_patterns else parent.injection_patterns,
        extends = None
    )

def _parse_metadata(data: dict) -> dict:
    return {
        "domain":  str(data.get("domain",  "")),
        "version": str(data.get("version", "")),
    }


def _parse_defaults(data: dict, source: str) -> dict:
    raw = data.get("defaults", {})
    if not isinstance(raw, dict):
        raise ConfigError(f"'defaults' must be a mapping in {source}")

    result = {}

    if "trust_level" in raw:
        tl = raw["trust_level"]
        if tl not in VALID_TRUST_LEVELS:
            raise ConfigError(
                f"'defaults.trust_level' must be one of "
                f"{sorted(VALID_TRUST_LEVELS)}, got {tl!r} in {source}"
            )
        result["trust_level"] = tl

    if "decision_on_unknowns" in raw:
        du = raw["decision_on_unknowns"]
        if du not in VALID_ON_UNKNOWNS:
            raise ConfigError(
                f"'defaults.decision_on_unknowns' must be one of "
                f"{sorted(VALID_ON_UNKNOWNS)}, got {du!r} in {source}"
            )
        result["decision_on_unknowns"] = du

    if "default_layers" in raw:
        dl = raw["default_layers"]
        if not isinstance(dl, list):
            raise ConfigError(
                f"'defaults.default_layers' must be a list in {source}"
            )
        result["default_layers"] = [str(x) for x in dl]

    # forward compatible — pass through unknown keys
    for k, v in raw.items():
        if k not in result:
            result[k] = v

    return result


def _parse_denied_list(data: dict, source: str) -> list[DeniedEntry]:
    raw = data.get("denied", [])
    if not isinstance(raw, list):
        raise ConfigError(f"'denied' must be a list in {source}")

    entries = []
    for e in raw:
        if not isinstance(e, dict):
            raise ConfigError(
                f"Each denied entry must be a mapping in {source}, got: {e!r}"
            )
        if "action" not in e or "resource" not in e:
            raise ConfigError(
                f"Denied entry missing 'action' or 'resource' in {source}: {e}"
            )
        entries.append(DeniedEntry(action=e["action"], resource=e["resource"]))

    return entries