# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, field_validator, model_validator

@dataclass(frozen=True)
class ValidationRequest:
    agent: str
    action: str
    resource: str
    params: dict[str, Any] =field(default_factory=dict)
    context: dict[str,Any] =field(default_factory=dict)

    def to_eval_dict(self)->dict:
        return {
            "agent":    self.agent,
            "action":   self.action,
            "resource": self.resource,
            "params":   self.params,
            "context":  self.context,
        }

class LayerStatus(str,Enum):
    PASS = "pass"
    BLOCK = "block"
    FLAG = "flag"

@dataclass
class LayerResult:
    status: LayerStatus
    layer: str
    reason: str = ""
    enrichments: dict[str, Any] = field(default_factory=dict)

    @property
    def blocked(self)->bool:
        return self.status == LayerStatus.BLOCK
    
    @property
    def flagged(self)->bool:
        return self.status == LayerStatus.FLAG
    
    def to_trace_entry(self)-> dict:
        entry: dict = {"status":self.status.value, "reason": self.reason}
        if self.enrichments:
            entry["enrichments"] = self.enrichments
        return entry
    
@dataclass
class ValidationResult:
    approval: bool
    reason: str
    layer_trace: dict[str, dict] = field(default_factory=dict)

    @classmethod
    def from_block(cls, layer_result: LayerResult, trace: dict[str, dict])->ValidationResult:
        return cls(approval=False, reason=layer_result.reason,layer_trace=trace)
    
    @classmethod
    def from_approve(cls,trace:dict[str,dict])->ValidationResult:
        return cls(approval=True,reason="approved",layer_trace=trace)
    
CONSTRAINT_OPERATORS = frozenset({"eq", "neq", "gte", "gt", "lte", "lt", "contains", "in", "not_in", "not_contains", "exists"})
VALID_LAYERS = {
    "l1_identity", "l2_injection", "l3_intent", "l4_memory", "l5_data", "l6_policy", "l9_scope"
}

class Constraint(BaseModel):
    param: str
    operator: str
    value: Any

    @field_validator("param")
    @classmethod
    def param_not_empty(cls, v:str)-> str:
        if not v.strip():
            raise ValueError("Constraint param must not be empty")
        return v.strip()
    
    @field_validator("operator")
    @classmethod
    def operator_valid(cls, v: str)-> str:
        if v not in CONSTRAINT_OPERATORS:
            raise ValueError(
                f"Constraint operator {v!r} is invalid "
                f"Must be one of the {','.join(sorted(CONSTRAINT_OPERATORS))}"
            )
        return v 
    
class ScopeEntry(BaseModel):
    action: str
    resource: str
    constraints: list[Constraint] = []
    layers: list[str] = []
    dedup: DedupConfig | None = None

    @field_validator("action", "resource")
    @classmethod
    def param_not_empty(cls, v:str)-> str:
        if not v.strip():
            raise ValueError("ScopeEntry 'action' and 'resource' must not be empty")
        return v.strip()
    
    @field_validator("layers")
    @classmethod
    def valid_layer(cls,v:list[str])-> list[str]:
        for layer in v:
            if layer not in VALID_LAYERS:
                raise ValueError(f"Layer {layer!r} defined is invalid. Must be one of the {VALID_LAYERS} .")
        return v

class DeniedEntry(BaseModel):
    action: str
    resource: str

    @field_validator("action", "resource")
    @classmethod
    def param_not_empty(cls, v:str)-> str:
        if not v.strip():
            raise ValueError("DeniedEntry fields must not be empty")
        return v.strip()
    
class IdentityConfig(BaseModel):
    require_caller: bool = False
    allowed_callers: list[str] = []
    
class RateLimit(BaseModel):
    resource: str
    limit: int
    window_seconds: int = 3600

class DedupConfig(BaseModel):
    identity_params: list[str]
    ttl_seconds: int = 86400

class AgentConfig(BaseModel):
    model_config = {"extra": "ignore"}

    agent: str = ""
    extends: Optional[str] = None
    role: str = ""
    trust_level: str = "low"
    default_layers: list[str]         = []
    scope:          list[ScopeEntry]  = []
    denied:         list[DeniedEntry] = []
    policies: tuple = ()
    injection_patterns: dict = {}
    identity: IdentityConfig = IdentityConfig()
    rate_limits: list[RateLimit]  = []

    @field_validator("agent")
    @classmethod
    def agent_name_valid(cls, v: str) -> str:
        if not v:
            return v
        if not re.match(r"^[a-z][a-z0-9_]*$", v):
            raise ValueError(
                f"Agent name {v!r} must be snake_case"
            )
        return v
    
    @field_validator("trust_level")
    @classmethod
    def trust_level_valid(cls, v: str) -> str:
        valid = {"low", "medium", "high"}
        if v not in valid:
            raise ValueError(f"trust_level must be one of {sorted(valid)}, got {v!r}")
        return v
        
    @field_validator("default_layers")
    @classmethod
    def valid_layer(cls,v:list[str])-> list[str]:
        for layer in v:
            if layer not in VALID_LAYERS:
                raise ValueError(f"Layer {layer!r} defined is invalid. Must be one of the {VALID_LAYERS} .")
        return v
        
    @model_validator(mode="after")
    def does_not_extend_self(self)-> AgentConfig:
        if self.extends is not None:
            if self.agent and self.extends.strip() == self.agent:
                raise ValueError(f"Agent '{self.agent}' cannot extend itself")
        return self
    
# helper
def build_result(layer_results: list[LayerResult]) -> ValidationResult:
    trace = {lr.layer: lr.to_trace_entry() for lr in layer_results}
    for lr in layer_results:
        if lr.blocked:
            return ValidationResult.from_block(lr,trace)
        
    return ValidationResult.from_approve(trace)
