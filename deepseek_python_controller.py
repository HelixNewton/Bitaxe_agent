#!/usr/bin/env python3
"""
Bitaxe Controller - Advanced tuning automation for Bitaxe miners
Features:
- Rule-based and AI-assisted decision making
- Learning from historical performance
- Adaptive cooldown periods
- Circuit breaker for API failures
- Prometheus metrics export
- Configuration validation
- Thread-safe status file handling
"""

import argparse
import fcntl
import json
import logging
import os
import sys
import time
import re
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Tuple
from urllib import error, request
from functools import wraps
from collections import defaultdict

# Optional imports with fallbacks
try:
    from prometheus_client import Counter, Gauge, Histogram, start_http_server
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

try:
    from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
    TENACITY_AVAILABLE = True
except ImportError:
    TENACITY_AVAILABLE = False


# ============================================================================
# Utility Functions
# ============================================================================

def app_base_dir() -> str:
    """Get application base directory (works with PyInstaller)"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def env_bool(name: str, default: bool) -> bool:
    """Parse boolean from environment variable"""
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_int(name: str, default: int) -> int:
    """Parse integer from environment variable"""
    value = os.getenv(name)
    return int(value) if value is not None else default


def env_float(name: str, default: float) -> float:
    """Parse float from environment variable"""
    value = os.getenv(name)
    return float(value) if value is not None else default


def mask_sensitive_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Mask sensitive information for logging"""
    masked = data.copy()
    sensitive_keys = ['api_key', 'password', 'secret', 'token', 'AI_API_KEY', 'OPENAI_API_KEY']
    for key in sensitive_keys:
        if key in masked:
            masked[key] = '***MASKED***'
        key_lower = key.lower()
        for data_key in list(masked.keys()):
            if key_lower in data_key.lower():
                masked[data_key] = '***MASKED***'
    return masked


def openai_safe_config(config: 'Config') -> Dict[str, Any]:
    """Return only the config fields the model needs for a tuning decision."""
    return {
        "mode": config.mode,
        "dry_run": config.dry_run,
        "min_frequency": config.min_frequency,
        "max_frequency": config.max_frequency,
        "absolute_max_frequency": config.absolute_max_frequency,
        "freq_step": config.freq_step,
        "min_voltage": config.min_voltage,
        "max_voltage": config.max_voltage,
        "absolute_max_voltage": config.absolute_max_voltage,
        "voltage_step": config.voltage_step,
        "target_temp_c": config.target_temp_c,
        "hot_temp_c": config.hot_temp_c,
        "emergency_temp_c": config.emergency_temp_c,
        "max_vr_temp_c": config.max_vr_temp_c,
        "min_input_voltage_mv": config.min_input_voltage_mv,
        "max_power_w": config.max_power_w,
        "climb_power_ratio": config.climb_power_ratio,
        "climb_power_gate_w": config.max_power_w * config.climb_power_ratio,
        "min_fan_percent": config.min_fan_percent,
        "max_fan_percent": config.max_fan_percent,
        "max_error_percentage": config.max_error_percentage,
        "max_domain_spread_percentage": config.max_domain_spread_percentage,
        "critical_domain_spread_percentage": config.critical_domain_spread_percentage,
        "step_cooldown_seconds": config.step_cooldown_seconds,
        "adaptive_cooldown_enabled": config.adaptive_cooldown_enabled,
    }


@contextmanager
def locked_file(path: str, mode: str = 'w'):
    """Context manager for thread-safe file operations"""
    with open(path, mode) as f:
        try:
            fcntl.flock(f, fcntl.LOCK_EX)
            yield f
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


# ============================================================================
# Custom Exceptions
# ============================================================================

class BitaxeError(Exception):
    """Base exception for Bitaxe controller"""
    pass


class BitaxeConnectionError(BitaxeError):
    """Raised when connection to Bitaxe fails"""
    pass


class BitaxeInvalidStateError(BitaxeError):
    """Raised when miner state is invalid"""
    pass


class BitaxeConfigurationError(BitaxeError):
    """Raised when configuration is invalid"""
    pass


class CircuitBreakerOpenError(BitaxeError):
    """Raised when circuit breaker is open"""
    pass


# ============================================================================
# Circuit Breaker
# ============================================================================

class CircuitBreaker:
    """Circuit breaker pattern for API calls"""
    
    def __init__(self, failure_threshold: int = 3, recovery_timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failures = 0
        self.last_failure_time: Optional[datetime] = None
        self.state = "closed"  # closed, open, half-open
    
    def call(self, func, *args, **kwargs):
        """Execute function with circuit breaker protection"""
        if self.state == "open":
            if datetime.now() - self.last_failure_time > timedelta(seconds=self.recovery_timeout):
                self.state = "half-open"
                logging.info("Circuit breaker transitioned to half-open")
            else:
                raise CircuitBreakerOpenError(
                    f"Circuit breaker is open (failed {self.failures} times)"
                )
        
        try:
            result = func(*args, **kwargs)
            if self.failures:
                self.failures = 0
                self.last_failure_time = None
            if self.state == "half-open":
                self.state = "closed"
                logging.info("Circuit breaker closed after successful call")
            return result
        except Exception as e:
            self.failures += 1
            self.last_failure_time = datetime.now()
            if self.failures >= self.failure_threshold:
                self.state = "open"
                logging.warning(
                    f"Circuit breaker opened after {self.failures} failures"
                )
            raise e
    
    def reset(self):
        """Reset circuit breaker"""
        self.failures = 0
        self.last_failure_time = None
        self.state = "closed"
        logging.info("Circuit breaker reset")


# ============================================================================
# Metrics Collection
# ============================================================================

@dataclass
class Metrics:
    """Performance metrics collector"""
    decisions: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    actions_taken: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    api_latencies: List[float] = field(default_factory=list)
    errors: List[Tuple[str, str]] = field(default_factory=list)  # (error_type, timestamp)
    start_time: float = field(default_factory=time.time)
    
    def record_decision(self, decision_type: str):
        """Record a decision made by the controller"""
        self.decisions[decision_type] += 1
    
    def record_action(self, action: str):
        """Record an action taken"""
        self.actions_taken[action] += 1
    
    def record_api_latency(self, latency: float):
        """Record API call latency"""
        self.api_latencies.append(latency)
        # Keep only last 1000 samples
        if len(self.api_latencies) > 1000:
            self.api_latencies = self.api_latencies[-1000:]
    
    def record_error(self, error_type: str):
        """Record an error occurrence"""
        self.errors.append((error_type, datetime.now().isoformat()))
        # Keep only last 100 errors
        if len(self.errors) > 100:
            self.errors = self.errors[-100:]
    
    def get_summary(self) -> Dict[str, Any]:
        """Get metrics summary"""
        total_decisions = sum(self.decisions.values())
        return {
            "total_decisions": total_decisions,
            "decision_breakdown": dict(self.decisions),
            "action_breakdown": dict(self.actions_taken),
            "avg_api_latency": sum(self.api_latencies) / len(self.api_latencies) if self.api_latencies else 0,
            "error_count": len(self.errors),
            "error_rate": len(self.errors) / total_decisions if total_decisions > 0 else 0,
            "uptime_seconds": time.time() - self.start_time,
        }


# ============================================================================
# Prometheus Metrics (Optional)
# ============================================================================

class PrometheusExporter:
    """Export metrics to Prometheus"""
    
    def __init__(self, port: int = 8000):
        self.port = port
        self.enabled = PROMETHEUS_AVAILABLE
        self.metrics = {}
        
        if self.enabled:
            self._init_metrics()
            start_http_server(port)
            logging.info(f"Prometheus metrics available on port {port}")
    
    def _init_metrics(self):
        """Initialize Prometheus metrics"""
        self.metrics['temperature'] = Gauge('bitaxe_temperature_celsius', 'ASIC temperature')
        self.metrics['vr_temperature'] = Gauge('bitaxe_vr_temperature_celsius', 'Voltage regulator temperature')
        self.metrics['hashrate'] = Gauge('bitaxe_hashrate_gh', 'Current hashrate in GH/s')
        self.metrics['hashrate_10m'] = Gauge('bitaxe_hashrate_10m_gh', '10-minute average hashrate in GH/s')
        self.metrics['power'] = Gauge('bitaxe_power_watts', 'Power consumption in watts')
        self.metrics['frequency'] = Gauge('bitaxe_frequency_mhz', 'Core frequency in MHz')
        self.metrics['voltage'] = Gauge('bitaxe_voltage_mv', 'Core voltage in mV')
        self.metrics['fan_speed'] = Gauge('bitaxe_fan_percent', 'Fan speed percentage')
        self.metrics['error_percentage'] = Gauge('bitaxe_error_percentage', 'Hardware error percentage')
        self.metrics['performance_score'] = Gauge('bitaxe_performance_score', 'Performance score')
        
        self.metrics['decisions_total'] = Counter('bitaxe_decisions_total', 'Total decisions made', ['type'])
        self.metrics['actions_total'] = Counter('bitaxe_actions_total', 'Total actions taken', ['action'])
        self.metrics['decision_latency'] = Histogram('bitaxe_decision_latency_seconds', 'Decision latency')
    
    def update_state(self, state: 'MinerState', score: float):
        """Update metrics from miner state"""
        if not self.enabled:
            return
        
        self.metrics['temperature'].set(state.temperature_c)
        self.metrics['vr_temperature'].set(state.vr_temperature_c)
        self.metrics['hashrate'].set(state.hashrate_gh)
        self.metrics['hashrate_10m'].set(state.hashrate_10m_gh)
        self.metrics['power'].set(state.power_w)
        self.metrics['frequency'].set(state.frequency_mhz)
        self.metrics['voltage'].set(state.voltage_mv)
        self.metrics['fan_speed'].set(state.fan_percent)
        self.metrics['error_percentage'].set(state.error_percentage)
        self.metrics['performance_score'].set(score)
    
    def record_decision(self, decision_type: str):
        """Record a decision"""
        if self.enabled:
            self.metrics['decisions_total'].labels(type=decision_type).inc()
    
    def record_action(self, action: str):
        """Record an action"""
        if self.enabled:
            self.metrics['actions_total'].labels(action=action).inc()
    
    def record_latency(self, latency: float):
        """Record decision latency"""
        if self.enabled:
            self.metrics['decision_latency'].observe(latency)


# ============================================================================
# Configuration
# ============================================================================

@dataclass
class Config:
    """Controller configuration with validation"""
    bitaxe_url: str
    loop_seconds: int = 30
    mode: str = "rules"
    dry_run: bool = False
    auto_fan: bool = False
    min_frequency: int = 425
    max_frequency: int = 600
    absolute_max_frequency: int = 625
    freq_step: int = 25
    min_voltage: int = 1100
    max_voltage: int = 1300
    absolute_max_voltage: int = 1150
    voltage_step: int = 10
    target_temp_c: float = 58.0
    hot_temp_c: float = 64.0
    emergency_temp_c: float = 70.0
    absolute_max_emergency_temp_c: float = 70.0
    cool_temp_c: float = 52.0
    max_vr_temp_c: float = 90.0
    absolute_max_vr_temp_c: float = 75.0
    min_input_voltage_mv: int = 4800
    max_power_w: float = 18.0
    absolute_max_power_w: float = 18.0
    climb_power_ratio: float = 0.90
    min_fan_percent: int = 50
    max_fan_percent: int = 100
    step_cooldown_seconds: int = 180
    min_hashrate_gh: float = 0.0
    use_asic_options: bool = False
    max_error_percentage: float = 20.0
    max_domain_spread_percentage: float = 10.0
    critical_domain_spread_percentage: float = 18.0
    domain_spread_polls: int = 2
    learning_enabled: bool = True
    learning_min_samples: int = 3
    learning_bad_limit: int = 2
    learning_restore_margin: float = 0.03
    learning_efficiency_weight: float = 0.25
    adaptive_cooldown_enabled: bool = True
    adaptive_min_cooldown_seconds: int = 45
    adaptive_max_cooldown_seconds: int = 240
    adaptive_stable_samples: int = 8
    status_file: str = os.path.join(app_base_dir(), "status.json")
    learning_file: str = os.path.join(app_base_dir(), "learning.json")
    ai_api_url: Optional[str] = None
    ai_api_key: Optional[str] = None
    ai_model: Optional[str] = None
    prometheus_port: int = 8000
    enable_prometheus: bool = False
    circuit_breaker_threshold: int = 3
    circuit_breaker_timeout: int = 60

    @classmethod
    def from_env(cls) -> "Config":
        """Create configuration from environment variables"""
        bitaxe_url = os.getenv("BITAXE_URL")
        if not bitaxe_url:
            raise SystemExit("BITAXE_URL is required")
        
        config = cls(
            bitaxe_url=bitaxe_url.rstrip("/"),
            loop_seconds=env_int("BITAXE_LOOP_SECONDS", 30),
            mode=os.getenv("BITAXE_MODE", "rules").strip().lower(),
            dry_run=env_bool("BITAXE_DRY_RUN", False),
            auto_fan=env_bool("BITAXE_AUTO_FAN", False),
            min_frequency=env_int("BITAXE_MIN_FREQUENCY", 425),
            max_frequency=env_int("BITAXE_MAX_FREQUENCY", 600),
            absolute_max_frequency=env_int("BITAXE_ABSOLUTE_MAX_FREQUENCY", 625),
            freq_step=env_int("BITAXE_FREQ_STEP", 25),
            min_voltage=env_int("BITAXE_MIN_VOLTAGE", 1100),
            max_voltage=env_int("BITAXE_MAX_VOLTAGE", 1300),
            absolute_max_voltage=env_int("BITAXE_ABSOLUTE_MAX_VOLTAGE", 1150),
            voltage_step=env_int("BITAXE_VOLTAGE_STEP", 10),
            target_temp_c=env_float("BITAXE_TARGET_TEMP_C", 58.0),
            hot_temp_c=env_float("BITAXE_HOT_TEMP_C", 64.0),
            emergency_temp_c=env_float("BITAXE_EMERGENCY_TEMP_C", 70.0),
            absolute_max_emergency_temp_c=env_float("BITAXE_ABSOLUTE_MAX_EMERGENCY_TEMP_C", 70.0),
            cool_temp_c=env_float("BITAXE_COOL_TEMP_C", 52.0),
            max_vr_temp_c=env_float("BITAXE_MAX_VR_TEMP_C", 90.0),
            absolute_max_vr_temp_c=env_float("BITAXE_ABSOLUTE_MAX_VR_TEMP_C", 75.0),
            min_input_voltage_mv=env_int("BITAXE_MIN_INPUT_VOLTAGE_MV", 4800),
            max_power_w=env_float("BITAXE_MAX_POWER_W", 18.0),
            absolute_max_power_w=env_float("BITAXE_ABSOLUTE_MAX_POWER_W", 18.0),
            climb_power_ratio=env_float("BITAXE_CLIMB_POWER_RATIO", 0.90),
            min_fan_percent=env_int("BITAXE_MIN_FAN_PERCENT", 50),
            max_fan_percent=env_int("BITAXE_MAX_FAN_PERCENT", 100),
            step_cooldown_seconds=env_int("BITAXE_STEP_COOLDOWN_SECONDS", 180),
            min_hashrate_gh=env_float("BITAXE_MIN_HASHRATE_GH", 0.0),
            use_asic_options=env_bool("BITAXE_USE_ASIC_OPTIONS", False),
            max_error_percentage=env_float("BITAXE_MAX_ERROR_PERCENTAGE", 20.0),
            max_domain_spread_percentage=env_float("BITAXE_MAX_DOMAIN_SPREAD_PERCENTAGE", 10.0),
            critical_domain_spread_percentage=env_float("BITAXE_CRITICAL_DOMAIN_SPREAD_PERCENTAGE", 18.0),
            domain_spread_polls=env_int("BITAXE_DOMAIN_SPREAD_POLLS", 2),
            learning_enabled=env_bool("BITAXE_LEARNING_ENABLED", True),
            learning_min_samples=env_int("BITAXE_LEARNING_MIN_SAMPLES", 3),
            learning_bad_limit=env_int("BITAXE_LEARNING_BAD_LIMIT", 2),
            learning_restore_margin=env_float("BITAXE_LEARNING_RESTORE_MARGIN", 0.03),
            learning_efficiency_weight=env_float("BITAXE_LEARNING_EFFICIENCY_WEIGHT", 0.25),
            adaptive_cooldown_enabled=env_bool("BITAXE_ADAPTIVE_COOLDOWN_ENABLED", True),
            adaptive_min_cooldown_seconds=env_int("BITAXE_ADAPTIVE_MIN_COOLDOWN_SECONDS", 45),
            adaptive_max_cooldown_seconds=env_int("BITAXE_ADAPTIVE_MAX_COOLDOWN_SECONDS", 240),
            adaptive_stable_samples=env_int("BITAXE_ADAPTIVE_STABLE_SAMPLES", 8),
            status_file=os.getenv("BITAXE_STATUS_FILE", os.path.join(app_base_dir(), "status.json")),
            learning_file=os.getenv("BITAXE_LEARNING_FILE", os.path.join(app_base_dir(), "learning.json")),
            ai_api_url=os.getenv("AI_API_URL", "https://api.openai.com/v1/responses"),
            ai_api_key=os.getenv("AI_API_KEY") or os.getenv("OPENAI_API_KEY"),
            ai_model=os.getenv("AI_MODEL"),
            prometheus_port=env_int("PROMETHEUS_PORT", 8000),
            enable_prometheus=env_bool("ENABLE_PROMETHEUS", False),
            circuit_breaker_threshold=env_int("CIRCUIT_BREAKER_THRESHOLD", 3),
            circuit_breaker_timeout=env_int("CIRCUIT_BREAKER_TIMEOUT", 60),
        )
        config.validate()
        return config

    def validate(self) -> None:
        """Validate configuration consistency"""
        if self.mode not in {"rules", "openai"}:
            raise BitaxeConfigurationError(f"Invalid mode: {self.mode}. Must be 'rules' or 'openai'")
        
        if self.mode == "openai":
            if not self.ai_api_key:
                raise BitaxeConfigurationError("AI mode requires AI_API_KEY")
            if not self.ai_model:
                raise BitaxeConfigurationError("AI mode requires AI_MODEL")
        
        if self.min_frequency > self.max_frequency:
            raise BitaxeConfigurationError(
                f"min_frequency ({self.min_frequency}) > max_frequency ({self.max_frequency})"
            )
        
        if self.min_voltage > self.max_voltage:
            raise BitaxeConfigurationError(
                f"min_voltage ({self.min_voltage}) > max_voltage ({self.max_voltage})"
            )
        
        if self.target_temp_c >= self.hot_temp_c:
            raise BitaxeConfigurationError(
                f"target_temp_c ({self.target_temp_c}) must be < hot_temp_c ({self.hot_temp_c})"
            )
        
        if self.hot_temp_c >= self.emergency_temp_c:
            raise BitaxeConfigurationError(
                f"hot_temp_c ({self.hot_temp_c}) must be < emergency_temp_c ({self.emergency_temp_c})"
            )
        
        if self.min_fan_percent > self.max_fan_percent:
            raise BitaxeConfigurationError(
                f"min_fan_percent ({self.min_fan_percent}) > max_fan_percent ({self.max_fan_percent})"
            )
        
        # Apply bounds after validation
        self._apply_bounds()

    def _apply_bounds(self) -> None:
        """Apply absolute bounds to configuration values"""
        self.absolute_max_frequency = min(self.absolute_max_frequency, 625)
        self.absolute_max_voltage = min(self.absolute_max_voltage, 1150)
        self.absolute_max_emergency_temp_c = min(self.absolute_max_emergency_temp_c, 70.0)
        self.absolute_max_vr_temp_c = min(self.absolute_max_vr_temp_c, 75.0)
        self.absolute_max_power_w = min(self.absolute_max_power_w, 18.0)
        self.max_frequency = min(self.max_frequency, self.absolute_max_frequency)
        self.max_voltage = min(self.max_voltage, self.absolute_max_voltage)
        self.emergency_temp_c = min(self.emergency_temp_c, self.absolute_max_emergency_temp_c)
        self.max_vr_temp_c = min(self.max_vr_temp_c, self.absolute_max_vr_temp_c)
        self.max_power_w = min(self.max_power_w, self.absolute_max_power_w)
        self.climb_power_ratio = max(0.50, min(0.99, self.climb_power_ratio))
        self.min_frequency = min(self.min_frequency, self.max_frequency)
        self.min_voltage = min(self.min_voltage, self.max_voltage)
        self.hot_temp_c = min(self.hot_temp_c, self.emergency_temp_c)
        self.target_temp_c = min(self.target_temp_c, self.hot_temp_c)
        self.cool_temp_c = min(self.cool_temp_c, self.target_temp_c)


# ============================================================================
# Data Models
# ============================================================================

@dataclass
class MinerState:
    """Current miner state"""
    temperature_c: float
    vr_temperature_c: float
    frequency_mhz: int
    voltage_mv: int
    frequency_options: List[int]
    voltage_options: List[int]
    fan_percent: int
    hashrate_gh: float
    hashrate_10m_gh: float
    error_percentage: float
    domain_spread_percentage: float
    offline_domain_count: int
    power_w: float
    input_voltage_mv: int
    raw: Dict[str, Any]
    timestamp: float = field(default_factory=time.time)


@dataclass
class LearningRecord:
    """Learning record for a specific frequency/voltage combination"""
    frequency_mhz: int
    voltage_mv: int
    samples: int = 0
    stable_samples: int = 0
    unstable_samples: int = 0
    best_hashrate_gh: float = 0.0
    avg_hashrate_gh: float = 0.0
    best_hashrate_10m_gh: float = 0.0
    avg_hashrate_10m_gh: float = 0.0
    best_efficiency_gh_per_w: float = 0.0
    avg_efficiency_gh_per_w: float = 0.0
    best_score: float = 0.0
    avg_score: float = 0.0
    min_score: float = 0.0
    max_total_penalty: float = 0.0
    max_temperature_c: float = 0.0
    max_power_w: float = 0.0
    max_error_percentage: float = 0.0
    max_domain_spread_percentage: float = 0.0
    last_seen_at: str = ""
    last_unstable_at: str = ""

    @property
    def key(self) -> str:
        return f"{self.frequency_mhz}:{self.voltage_mv}"


class ControllerState(Enum):
    """Controller state machine states"""
    NORMAL = auto()
    COOLDOWN = auto()
    EMERGENCY = auto()
    LEARNING = auto()
    RECOVERY = auto()


# ============================================================================
# Helper Functions
# ============================================================================

def get_first_number(data: Dict[str, Any], *keys: str, default: float = 0.0) -> float:
    """Get first numeric value from dictionary using multiple keys"""
    for key in keys:
        if key in data and data[key] not in (None, ""):
            try:
                return float(data[key])
            except (TypeError, ValueError):
                continue
    return default


def clamp(value: int, low: int, high: int) -> int:
    """Clamp integer value between low and high"""
    return max(low, min(high, value))


def parse_int_list(value: Any) -> List[int]:
    """Parse list of integers from various formats"""
    if not isinstance(value, list):
        return []
    out = []
    for item in value:
        try:
            out.append(int(item))
        except (TypeError, ValueError):
            continue
    return sorted(set(out))


def parse_domain_metrics(data: Dict[str, Any]) -> Tuple[float, int]:
    """Parse domain spread percentage and offline domain count"""
    domains = data.get("hashrateMonitor", {}).get("asics", [{}])[0].get("domains", [])
    if not isinstance(domains, list):
        return 0.0, 0
    
    numeric_domains: List[float] = []
    for item in domains:
        try:
            numeric_domains.append(float(item))
        except (TypeError, ValueError):
            numeric_domains.append(0.0)
    
    if not numeric_domains:
        return 0.0, 0
    
    active_domains = [value for value in numeric_domains if value > 0]
    offline_count = len(numeric_domains) - len(active_domains)
    
    if not active_domains:
        return 100.0, offline_count
    
    average = sum(active_domains) / len(active_domains)
    weakest = min(active_domains)
    spread = ((average - weakest) / average) * 100 if average > 0 else 0.0
    return spread, offline_count


def prev_setting(current: int, minimum: int, step: int, options: List[int], use_options: bool) -> int:
    """Get previous valid setting (decrease)"""
    if use_options and options:
        allowed = [value for value in options if minimum <= value < current]
        return allowed[-1] if allowed else max(minimum, min(options))
    return clamp(current - step, minimum, current)


def next_setting(current: int, maximum: int, step: int, options: List[int], use_options: bool) -> int:
    """Get next valid setting (increase)"""
    if use_options and options:
        allowed = [value for value in options if current < value <= maximum]
        return allowed[0] if allowed else min(maximum, max(options))
    return clamp(current + step, current, maximum)


def efficiency_gh_per_w(state: MinerState) -> float:
    """Calculate efficiency in GH/s per watt"""
    return state.hashrate_10m_gh / state.power_w if state.power_w > 0 else 0.0


def performance_metrics(state: MinerState, config: Config) -> Dict[str, float]:
    """Calculate detailed performance metrics"""
    stable_hashrate = state.hashrate_10m_gh or state.hashrate_gh
    efficiency = efficiency_gh_per_w(state)
    power_ratio = state.power_w / config.max_power_w if config.max_power_w and state.power_w else 0.0
    temp_ratio = state.temperature_c / config.hot_temp_c if config.hot_temp_c else 1.0
    fan_ratio = state.fan_percent / config.max_fan_percent if config.max_fan_percent else 1.0
    error_ratio = state.error_percentage / config.max_error_percentage if config.max_error_percentage else 1.0
    domain_ratio = (
        state.domain_spread_percentage / config.max_domain_spread_percentage
        if config.max_domain_spread_percentage
        else 1.0
    )
    
    base_score = stable_hashrate + (efficiency * config.learning_efficiency_weight)
    power_penalty = max(0.0, power_ratio - 0.92) * stable_hashrate * 2.0
    temp_penalty = max(0.0, temp_ratio - 0.90) * 120.0
    fan_penalty = max(0.0, fan_ratio - 0.85) * 80.0
    error_penalty = max(0.0, error_ratio - 0.20) * 80.0
    domain_penalty = max(0.0, domain_ratio - 0.70) * 100.0
    total_penalty = power_penalty + temp_penalty + fan_penalty + error_penalty + domain_penalty
    
    return {
        "stable_hashrate_gh": stable_hashrate,
        "efficiency_gh_per_w": efficiency,
        "base_score": base_score,
        "power_penalty": power_penalty,
        "temperature_penalty": temp_penalty,
        "fan_penalty": fan_penalty,
        "error_penalty": error_penalty,
        "domain_spread_penalty": domain_penalty,
        "total_penalty": total_penalty,
        "score": base_score - total_penalty,
    }


def performance_score(state: MinerState, config: Config) -> float:
    """Calculate overall performance score"""
    return performance_metrics(state, config)["score"]


def guardrail_metrics(state: MinerState, config: Config) -> Dict[str, Any]:
    """Summarize guardrail headroom and climb eligibility for prompts/status."""
    climb_power_gate = config.max_power_w * config.climb_power_ratio
    power_ratio = state.power_w / config.max_power_w if config.max_power_w and state.power_w else 0.0
    temp_ratio = state.temperature_c / config.hot_temp_c if config.hot_temp_c else 1.0
    vr_ratio = state.vr_temperature_c / config.max_vr_temp_c if config.max_vr_temp_c else 1.0
    error_ratio = state.error_percentage / config.max_error_percentage if config.max_error_percentage else 1.0
    domain_ratio = (
        state.domain_spread_percentage / config.max_domain_spread_percentage
        if config.max_domain_spread_percentage
        else 1.0
    )
    stable = (
        state.temperature_c < config.hot_temp_c
        and state.vr_temperature_c < config.max_vr_temp_c
        and (not state.input_voltage_mv or state.input_voltage_mv >= config.min_input_voltage_mv)
        and (not state.power_w or state.power_w <= config.max_power_w)
        and state.error_percentage < config.max_error_percentage
        and state.offline_domain_count == 0
        and state.domain_spread_percentage < config.max_domain_spread_percentage
    )
    can_climb = stable and state.temperature_c <= config.cool_temp_c and state.power_w < climb_power_gate
    return {
        "stable": stable,
        "can_climb_by_power": state.power_w < climb_power_gate,
        "can_climb": can_climb,
        "climb_power_gate_w": climb_power_gate,
        "power_ratio": power_ratio,
        "temperature_ratio": temp_ratio,
        "vr_temperature_ratio": vr_ratio,
        "error_ratio": error_ratio,
        "domain_spread_ratio": domain_ratio,
        "next_frequency_mhz": next_setting(
            state.frequency_mhz,
            config.max_frequency,
            config.freq_step,
            state.frequency_options,
            config.use_asic_options,
        ),
        "next_voltage_mv": next_setting(
            state.voltage_mv,
            config.max_voltage,
            config.voltage_step,
            state.voltage_options,
            config.use_asic_options,
        ),
    }


# ============================================================================
# Learning Store
# ============================================================================

class LearningStore:
    """Persistent storage for learning data"""
    
    def __init__(self, path: str):
        self.path = path
        self.records: Dict[str, LearningRecord] = {}
        self._frequency_index: Dict[int, List[str]] = {}
        self._voltage_index: Dict[int, List[str]] = {}
        self.load()
    
    def _update_indexes(self, record: LearningRecord):
        """Update search indexes"""
        key = record.key
        self._frequency_index.setdefault(record.frequency_mhz, []).append(key)
        self._voltage_index.setdefault(record.voltage_mv, []).append(key)
    
    def _remove_from_indexes(self, record: LearningRecord):
        """Remove from search indexes"""
        key = record.key
        if record.frequency_mhz in self._frequency_index:
            self._frequency_index[record.frequency_mhz] = [
                k for k in self._frequency_index[record.frequency_mhz] if k != key
            ]
        if record.voltage_mv in self._voltage_index:
            self._voltage_index[record.voltage_mv] = [
                k for k in self._voltage_index[record.voltage_mv] if k != key
            ]
    
    def load(self) -> None:
        """Load learning data from disk"""
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            for item in data.get("records", []):
                record = LearningRecord(**item)
                self.records[record.key] = record
                self._update_indexes(record)
        except Exception as exc:
            logging.warning("failed to load learning file %s: %s", self.path, exc)
    
    def save(self) -> None:
        """Save learning data to disk"""
        payload = {
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "records": [asdict(record) for record in self.records.values()],
        }
        tmp_path = f"{self.path}.tmp"
        try:
            with locked_file(tmp_path, 'w') as handle:
                json.dump(payload, handle, indent=2)
            os.replace(tmp_path, self.path)
        except Exception as exc:
            logging.error("Failed to save learning data: %s", exc)
    
    def record(self, state: MinerState, stable: bool, config: Config) -> LearningRecord:
        """Record a new sample for the current frequency/voltage"""
        key = f"{state.frequency_mhz}:{state.voltage_mv}"
        record = self.records.get(key)
        if record is None:
            record = LearningRecord(frequency_mhz=state.frequency_mhz, voltage_mv=state.voltage_mv)
            self.records[key] = record
            self._update_indexes(record)
        
        record.samples += 1
        if stable:
            record.stable_samples += 1
        else:
            record.unstable_samples += 1
            record.last_unstable_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        
        previous_total = record.samples - 1
        efficiency = efficiency_gh_per_w(state)
        metrics = performance_metrics(state, config)
        score = metrics["score"]
        
        # Update averages
        record.avg_hashrate_gh = (
            ((record.avg_hashrate_gh * previous_total) + state.hashrate_gh) / record.samples
            if record.samples > 1
            else state.hashrate_gh
        )
        record.avg_hashrate_10m_gh = (
            ((record.avg_hashrate_10m_gh * previous_total) + state.hashrate_10m_gh) / record.samples
            if record.samples > 1
            else state.hashrate_10m_gh
        )
        record.avg_efficiency_gh_per_w = (
            ((record.avg_efficiency_gh_per_w * previous_total) + efficiency) / record.samples
            if record.samples > 1
            else efficiency
        )
        record.avg_score = (
            ((record.avg_score * previous_total) + score) / record.samples
            if record.samples > 1
            else score
        )
        
        # Update best values
        record.best_hashrate_gh = max(record.best_hashrate_gh, state.hashrate_gh)
        record.best_hashrate_10m_gh = max(record.best_hashrate_10m_gh, state.hashrate_10m_gh)
        record.best_efficiency_gh_per_w = max(record.best_efficiency_gh_per_w, efficiency)
        record.best_score = max(record.best_score, score)
        record.min_score = score if record.samples == 1 else min(record.min_score, score)
        
        # Update maxima
        record.max_total_penalty = max(record.max_total_penalty, metrics["total_penalty"])
        record.max_temperature_c = max(record.max_temperature_c, state.temperature_c)
        record.max_power_w = max(record.max_power_w, state.power_w)
        record.max_error_percentage = max(record.max_error_percentage, state.error_percentage)
        record.max_domain_spread_percentage = max(record.max_domain_spread_percentage, state.domain_spread_percentage)
        record.last_seen_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        
        return record
    
    def get(self, frequency_mhz: int, voltage_mv: int) -> Optional[LearningRecord]:
        """Get record for specific frequency/voltage"""
        return self.records.get(f"{frequency_mhz}:{voltage_mv}")
    
    def get_by_frequency(self, frequency_mhz: int) -> List[LearningRecord]:
        """Get all records for a frequency"""
        return [self.records[k] for k in self._frequency_index.get(frequency_mhz, [])]
    
    def get_by_voltage(self, voltage_mv: int) -> List[LearningRecord]:
        """Get all records for a voltage"""
        return [self.records[k] for k in self._voltage_index.get(voltage_mv, [])]
    
    def best_stable(self, config: Config) -> Optional[LearningRecord]:
        """Find the best stable configuration based on learning data"""
        candidates = [
            record
            for record in self.records.values()
            if record.stable_samples >= config.learning_min_samples
            and record.unstable_samples < config.learning_bad_limit
            and config.min_frequency <= record.frequency_mhz <= config.max_frequency
            and config.min_voltage <= record.voltage_mv <= config.max_voltage
            and record.max_power_w <= config.max_power_w
            and record.max_temperature_c < config.hot_temp_c
            and record.max_error_percentage < config.max_error_percentage
            and record.max_domain_spread_percentage < config.max_domain_spread_percentage
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda record: (
            record.best_score, record.avg_score, record.best_hashrate_10m_gh, record.frequency_mhz
        ))
    
    def is_bad_candidate(self, frequency_mhz: int, voltage_mv: int, config: Config) -> bool:
        """Check if a frequency/voltage combination is known to be bad"""
        record = self.get(frequency_mhz, voltage_mv)
        return bool(record and record.unstable_samples >= config.learning_bad_limit and record.stable_samples == 0)
    
    def summary(self, config: Config) -> Dict[str, Any]:
        """Get summary of learning data"""
        best = self.best_stable(config)
        return {
            "enabled": config.learning_enabled,
            "record_count": len(self.records),
            "best_stable": asdict(best) if best else None,
            "bad_candidates": [
                asdict(record)
                for record in self.records.values()
                if record.unstable_samples >= config.learning_bad_limit and record.stable_samples == 0
            ],
        }


# ============================================================================
# Bitaxe Client
# ============================================================================

class BitaxeClient:
    """Client for interacting with Bitaxe API"""
    
    def __init__(self, base_url: str, timeout: int = 10):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.circuit_breaker = CircuitBreaker()
    
    def _request(self, method: str, path: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make HTTP request to Bitaxe API with retry logic"""
        
        def _do_request():
            body = None
            headers = {}
            if payload is not None:
                body = json.dumps(payload).encode("utf-8")
                headers["Content-Type"] = "application/json"
            
            req = request.Request(f"{self.base_url}{path}", data=body, headers=headers, method=method)
            
            start_time = time.time()
            try:
                with request.urlopen(req, timeout=self.timeout) as response:
                    latency = time.time() - start_time
                    text = response.read().decode("utf-8")
                    return json.loads(text) if text else {}
            except error.HTTPError as e:
                raise BitaxeConnectionError(f"HTTP {e.code}: {e.reason}") from e
            except error.URLError as e:
                raise BitaxeConnectionError(f"Connection failed: {e.reason}") from e
        
        # Apply circuit breaker
        return self.circuit_breaker.call(_do_request)
    
    def get_info(self) -> Dict[str, Any]:
        """Get system info"""
        return self._request("GET", "/api/system/info")
    
    def get_asic(self) -> Dict[str, Any]:
        """Get ASIC info"""
        return self._request("GET", "/api/system/asic")
    
    def patch_system(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Update system settings"""
        return self._request("PATCH", "/api/system", payload)
    
    def health_check(self) -> bool:
        """Check if Bitaxe is reachable"""
        try:
            self.get_info()
            return True
        except Exception:
            return False


# ============================================================================
# AI Advisor
# ============================================================================

class AiAdvisor:
    """AI-powered advisor for tuning decisions"""
    
    def __init__(self, config: Config):
        self.url = config.ai_api_url
        self.api_key = config.ai_api_key
        self.model = config.ai_model
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=config.circuit_breaker_threshold,
            recovery_timeout=config.circuit_breaker_timeout
        )
    
    def extract_output_text(self, data: Dict[str, Any]) -> str:
        """Extract text output from various response formats"""
        if data.get("status") == "incomplete":
            reason = data.get("incomplete_details", {}).get("reason", "unknown")
            raise RuntimeError(f"AI response incomplete: {reason}")

        if data.get("output_text"):
            return str(data["output_text"]).strip()
        
        chunks: List[str] = []
        for item in data.get("output", []):
            if not isinstance(item, dict):
                continue
            for content in item.get("content", []):
                if not isinstance(content, dict):
                    continue
                refusal = content.get("refusal")
                if refusal:
                    raise RuntimeError(f"AI response refused: {refusal}")
                text = content.get("text")
                if text:
                    chunks.append(str(text))
        return "".join(chunks).strip()
    
    def _validate_action(self, action: Dict[str, Any]) -> bool:
        """Validate AI response structure"""
        required_fields = ["action", "reason"]
        if not all(field in action for field in required_fields):
            logging.error(f"AI response missing required fields: {action}")
            return False
        
        valid_actions = ["hold", "raise_freq", "lower_freq", "raise_voltage", "lower_voltage", "set_fan"]
        if action["action"] not in valid_actions:
            logging.error(f"Invalid action in AI response: {action['action']}")
            return False
        
        if action["action"] == "set_fan":
            target_fan = action.get("target_fan_percent")
            if target_fan is None or not isinstance(target_fan, (int, float)):
                logging.error(f"set_fan action missing target_fan_percent: {action}")
                return False
        
        return True
    
    def decide(self, state: MinerState, config: Config, learning: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Get AI recommendation for next action"""
        if not self.api_key or not self.model:
            raise RuntimeError("AI mode requires AI_API_KEY and AI_MODEL")
        
        safe_config = openai_safe_config(config)
        metrics = performance_metrics(state, config)
        guardrails = guardrail_metrics(state, config)
        allowed_actions = ["hold", "lower_freq", "lower_voltage", "set_fan"]
        if guardrails["can_climb"]:
            allowed_actions.extend(["raise_freq", "raise_voltage"])
        
        prompt = {
            "task": "Recommend the next Bitaxe tuning action.",
            "rules": {
                "return_json_only": True,
                "allowed_actions": allowed_actions,
                "one_step_limit": True,
                "prefer_cooling_over_performance": True,
                "never_raise_when_can_climb_false": True,
                "hard_caps_are_authoritative": True,
            },
            "config": safe_config,
            "state": {
                "temperature_c": state.temperature_c,
                "vr_temperature_c": state.vr_temperature_c,
                "frequency_mhz": state.frequency_mhz,
                "voltage_mv": state.voltage_mv,
                "fan_percent": state.fan_percent,
                "hashrate_gh": state.hashrate_gh,
                "hashrate_10m_gh": state.hashrate_10m_gh,
                "efficiency_gh_per_w": efficiency_gh_per_w(state),
                "performance_score": metrics["score"],
                "score_penalty": metrics["total_penalty"],
                "power_w": state.power_w,
                "input_voltage_mv": state.input_voltage_mv,
                "error_percentage": state.error_percentage,
                "domain_spread_percentage": state.domain_spread_percentage,
                "offline_domain_count": state.offline_domain_count,
            },
            "guardrails": guardrails,
            "learning": learning or {},
            "response_schema": {
                "action": "hold|raise_freq|lower_freq|raise_voltage|lower_voltage|set_fan",
                "reason": "short string",
                "target_fan_percent": "integer or null",
            },
        }
        
        payload = {
            "model": self.model,
            "input": [
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "input_text",
                            "text": "You are a conservative hardware tuning controller. Respond with JSON only.",
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": json.dumps(prompt)}],
                },
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "bitaxe_tuning_action",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "action": {
                                "type": "string",
                                "enum": allowed_actions,
                            },
                            "reason": {"type": "string"},
                            "target_fan_percent": {
                                "anyOf": [
                                    {"type": "integer"},
                                    {"type": "null"},
                                ]
                            },
                        },
                        "required": ["action", "reason", "target_fan_percent"],
                        "additionalProperties": False,
                    },
                }
            },
        }
        
        def _call_api():
            req = request.Request(
                self.url,
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            with request.urlopen(req, timeout=30) as response:
                text = response.read().decode("utf-8")
                return json.loads(text)
        
        response = self.circuit_breaker.call(_call_api)
        raw = self.extract_output_text(response)
        
        if not raw:
            raise RuntimeError(f"AI response did not contain output_text: {response}")
        
        action = json.loads(raw)
        if not self._validate_action(action):
            raise ValueError(f"Invalid AI response: {action}")
        
        return action


# ============================================================================
# Main Controller
# ============================================================================

class Controller:
    """Main controller for Bitaxe tuning"""
    
    def __init__(self, config: Config):
        self.config = config
        self.client = BitaxeClient(config.bitaxe_url)
        self.ai = AiAdvisor(config) if config.mode == "openai" else None
        self.learning = LearningStore(config.learning_file)
        self.metrics = Metrics()
        self.prometheus = PrometheusExporter(config.prometheus_port) if config.enable_prometheus else None
        
        self.last_change_at = 0.0
        self.last_applied: Dict[str, Any] = {}
        self.last_state: Optional[MinerState] = None
        self.last_decision: Optional[Dict[str, Any]] = None
        self.last_error: Optional[str] = None
        self.domain_spread_breach_count = 0
        self.domain_spread_critical_count = 0
        self.state_machine_state = ControllerState.NORMAL
        self.decision_count = 0
        self.successful_actions = 0
        self.start_time = time.time()
    
    def is_state_stable(self, state: MinerState) -> bool:
        """Check if current state is stable"""
        if state.temperature_c >= self.config.hot_temp_c:
            return False
        if state.vr_temperature_c >= self.config.max_vr_temp_c:
            return False
        if state.input_voltage_mv and state.input_voltage_mv < self.config.min_input_voltage_mv:
            return False
        if state.power_w and state.power_w > self.config.max_power_w:
            return False
        if state.error_percentage >= self.config.max_error_percentage:
            return False
        if state.offline_domain_count > 0:
            return False
        if state.domain_spread_percentage >= self.config.max_domain_spread_percentage:
            return False
        return True
    
    def record_learning(self, state: MinerState) -> None:
        """Record current state for learning"""
        if not self.config.learning_enabled:
            return
        stable = self.is_state_stable(state)
        record = self.learning.record(state, stable, self.config)
        self.learning.save()
        logging.info(
            "learning freq=%sMHz volt=%smV stable=%s samples=%s best_hash=%.2fGH best_score=%.2f",
            record.frequency_mhz,
            record.voltage_mv,
            stable,
            record.samples,
            record.best_hashrate_gh,
            record.best_score,
        )
    
    def parse_state(self, info: Dict[str, Any], asic: Dict[str, Any]) -> MinerState:
        """Parse API responses into MinerState object"""
        merged = dict(info)
        merged.update(asic)
        
        temp = get_first_number(merged, "temp", "temperature", "ASIC_temp", "asic_temp", default=0.0)
        vr_temp = get_first_number(merged, "vrTemp", "vr_temp", "voltage_regulator_temp", default=0.0)
        freq = int(get_first_number(merged, "frequency", "freq", default=0.0))
        volt = int(get_first_number(merged, "coreVoltage", "core_voltage", "asic_voltage", default=0.0))
        frequency_options = parse_int_list(merged.get("frequencyOptions"))
        voltage_options = parse_int_list(merged.get("voltageOptions"))
        fan = int(get_first_number(merged, "fanSpeed", "fan_speed", "fanspeed", default=0.0))
        hashrate = get_first_number(
            merged,
            "hashRate_1m",
            "hashRate",
            "hashrate",
            "hashRate1m",
            "hashrate1m",
            "hashRateGH",
            default=0.0,
        )
        hashrate_10m = get_first_number(
            merged, "hashRate_10m", "hashrate_10m", "hashRate10m", "hashrate10m", default=hashrate
        )
        error_percentage = get_first_number(merged, "errorPercentage", "error_percentage", default=0.0)
        domain_spread_percentage, offline_domain_count = parse_domain_metrics(merged)
        power = get_first_number(merged, "power", "power_w", "powerDraw", default=0.0)
        input_mv = int(get_first_number(merged, "voltage", "inputVoltage", "input_voltage", default=0.0))
        
        return MinerState(
            temperature_c=temp,
            vr_temperature_c=vr_temp,
            frequency_mhz=freq,
            voltage_mv=volt,
            frequency_options=frequency_options,
            voltage_options=voltage_options,
            fan_percent=fan,
            hashrate_gh=hashrate,
            hashrate_10m_gh=hashrate_10m,
            error_percentage=error_percentage,
            domain_spread_percentage=domain_spread_percentage,
            offline_domain_count=offline_domain_count,
            power_w=power,
            input_voltage_mv=input_mv,
            raw=merged,
        )
    
    def build_patch(
        self, *, frequency: Optional[int] = None, voltage: Optional[int] = None, fan_percent: Optional[int] = None
    ) -> Dict[str, Any]:
        """Build patch payload for API request"""
        payload: Dict[str, Any] = {}
        if frequency is not None:
            payload["frequency"] = clamp(int(frequency), self.config.min_frequency, self.config.max_frequency)
        if voltage is not None:
            payload["coreVoltage"] = clamp(int(voltage), self.config.min_voltage, self.config.max_voltage)
        if fan_percent is not None:
            payload["fanspeed"] = clamp(int(fan_percent), self.config.min_fan_percent, self.config.max_fan_percent)
            payload["autofanspeed"] = False
        elif self.config.auto_fan:
            payload["autofanspeed"] = True
        return payload
    
    def headroom(self, state: MinerState) -> Dict[str, float]:
        """Calculate headroom for various metrics"""
        return {
            "temperature": state.temperature_c / self.config.hot_temp_c if self.config.hot_temp_c else 1.0,
            "vr_temperature": state.vr_temperature_c / self.config.max_vr_temp_c if self.config.max_vr_temp_c else 1.0,
            "power": state.power_w / self.config.max_power_w if self.config.max_power_w and state.power_w else 0.0,
            "error": state.error_percentage / self.config.max_error_percentage if self.config.max_error_percentage else 1.0,
            "domain_spread": state.domain_spread_percentage / self.config.max_domain_spread_percentage if self.config.max_domain_spread_percentage else 1.0,
        }
    
    def adaptive_cooldown_seconds(self, state: Optional[MinerState] = None) -> int:
        """Calculate adaptive cooldown period based on current state"""
        base = self.config.step_cooldown_seconds
        if not self.config.adaptive_cooldown_enabled or state is None:
            return base
        
        headroom = self.headroom(state)
        if (
            not self.is_state_stable(state)
            or headroom["temperature"] >= 0.96
            or headroom["vr_temperature"] >= 0.96
            or headroom["power"] >= 0.95
            or headroom["error"] >= 0.50
            or headroom["domain_spread"] >= 0.75
        ):
            return max(base, self.config.adaptive_max_cooldown_seconds)
        
        record = self.learning.get(state.frequency_mhz, state.voltage_mv)
        has_stable_history = bool(record and record.stable_samples >= self.config.adaptive_stable_samples)
        if (
            has_stable_history
            and state.temperature_c <= self.config.cool_temp_c
            and headroom["power"] <= 0.88
            and headroom["error"] <= 0.25
            and headroom["domain_spread"] <= 0.50
        ):
            return min(base, self.config.adaptive_min_cooldown_seconds)
        
        return base
    
    def can_change(self, state: Optional[MinerState] = None) -> bool:
        """Check if changes are allowed based on cooldown"""
        return (time.time() - self.last_change_at) >= self.adaptive_cooldown_seconds(state)
    
    def desired_fan(self, state: MinerState) -> Optional[int]:
        """Calculate desired fan speed based on temperatures"""
        if self.config.auto_fan:
            return None
        if state.temperature_c >= self.config.hot_temp_c or state.vr_temperature_c >= self.config.max_vr_temp_c - 5:
            return self.config.max_fan_percent
        if state.temperature_c >= self.config.target_temp_c:
            return clamp(self.config.min_fan_percent + 20, self.config.min_fan_percent, self.config.max_fan_percent)
        return self.config.min_fan_percent
    
    def update_domain_spread_tracking(self, state: MinerState) -> None:
        """Update domain spread breach counters"""
        if state.offline_domain_count > 0 or state.domain_spread_percentage >= self.config.critical_domain_spread_percentage:
            self.domain_spread_critical_count += 1
        else:
            self.domain_spread_critical_count = 0
        
        if state.offline_domain_count > 0 or state.domain_spread_percentage >= self.config.max_domain_spread_percentage:
            self.domain_spread_breach_count += 1
        else:
            self.domain_spread_breach_count = 0
    
    def learned_restore_decision(self, state: MinerState, fan: Optional[int]) -> Optional[Dict[str, Any]]:
        """Check if we should restore to a previously learned good configuration"""
        if not self.config.learning_enabled or not self.can_change(state) or not self.is_state_stable(state):
            return None
        
        best = self.learning.best_stable(self.config)
        if not best:
            return None
        
        if best.frequency_mhz == state.frequency_mhz and best.voltage_mv == state.voltage_mv:
            return None
        
        current_score = performance_score(state, self.config)
        if current_score >= best.best_score * (1.0 - self.config.learning_restore_margin):
            return None
        
        if best.frequency_mhz != state.frequency_mhz:
            target_freq = (
                next_setting(
                    state.frequency_mhz,
                    min(best.frequency_mhz, self.config.max_frequency),
                    self.config.freq_step,
                    state.frequency_options,
                    self.config.use_asic_options,
                )
                if best.frequency_mhz > state.frequency_mhz
                else prev_setting(
                    state.frequency_mhz,
                    max(best.frequency_mhz, self.config.min_frequency),
                    self.config.freq_step,
                    state.frequency_options,
                    self.config.use_asic_options,
                )
            )
            return {
                "reason": "learning restore toward best stable frequency",
                "patch": self.build_patch(frequency=target_freq, fan_percent=fan),
            }
        
        if best.voltage_mv != state.voltage_mv:
            target_voltage = (
                next_setting(
                    state.voltage_mv,
                    min(best.voltage_mv, self.config.max_voltage),
                    self.config.voltage_step,
                    state.voltage_options,
                    self.config.use_asic_options,
                )
                if best.voltage_mv > state.voltage_mv
                else prev_setting(
                    state.voltage_mv,
                    max(best.voltage_mv, self.config.min_voltage),
                    self.config.voltage_step,
                    state.voltage_options,
                    self.config.use_asic_options,
                )
            )
            return {
                "reason": "learning restore toward best stable voltage",
                "patch": self.build_patch(voltage=target_voltage, fan_percent=fan),
            }
        
        return None
    
    def decide_rules(self, state: MinerState) -> Dict[str, Any]:
        """Make decision based on rules engine"""
        fan = self.desired_fan(state)
        self.update_domain_spread_tracking(state)
        
        # Check frequency limits
        if state.frequency_mhz > self.config.max_frequency:
            return {
                "reason": "frequency above configured ceiling",
                "patch": self.build_patch(frequency=self.config.max_frequency, fan_percent=fan),
            }
        
        # Check voltage limits
        if state.voltage_mv > self.config.max_voltage:
            return {
                "reason": "voltage above configured ceiling",
                "patch": self.build_patch(voltage=self.config.max_voltage, fan_percent=fan),
            }
        
        # Critical domain instability
        if self.domain_spread_critical_count >= self.config.domain_spread_polls:
            return {
                "reason": "domain instability critical; strong rollback",
                "patch": self.build_patch(
                    frequency=prev_setting(
                        prev_setting(
                            state.frequency_mhz,
                            self.config.min_frequency,
                            self.config.freq_step,
                            state.frequency_options,
                            self.config.use_asic_options,
                        ),
                        self.config.min_frequency,
                        self.config.freq_step,
                        state.frequency_options,
                        self.config.use_asic_options,
                    ),
                    fan_percent=self.config.max_fan_percent if not self.config.auto_fan else fan,
                ),
            }
        
        # Domain instability
        if self.domain_spread_breach_count >= self.config.domain_spread_polls:
            return {
                "reason": "domain instability elevated; rollback frequency",
                "patch": self.build_patch(
                    frequency=prev_setting(
                        state.frequency_mhz,
                        self.config.min_frequency,
                        self.config.freq_step,
                        state.frequency_options,
                        self.config.use_asic_options,
                    ),
                    fan_percent=fan,
                ),
            }
        
        # Critical error rate
        if state.error_percentage >= self.config.max_error_percentage * 1.5:
            return {
                "reason": "hardware error rate critical; strong rollback",
                "patch": self.build_patch(
                    frequency=prev_setting(
                        prev_setting(
                            state.frequency_mhz,
                            self.config.min_frequency,
                            self.config.freq_step,
                            state.frequency_options,
                            self.config.use_asic_options,
                        ),
                        self.config.min_frequency,
                        self.config.freq_step,
                        state.frequency_options,
                        self.config.use_asic_options,
                    ),
                    fan_percent=fan,
                ),
            }
        
        # High error rate
        if state.error_percentage >= self.config.max_error_percentage:
            return {
                "reason": "hardware error rate high; rollback frequency",
                "patch": self.build_patch(
                    frequency=prev_setting(
                        state.frequency_mhz,
                        self.config.min_frequency,
                        self.config.freq_step,
                        state.frequency_options,
                        self.config.use_asic_options,
                    ),
                    fan_percent=fan,
                ),
            }
        
        # Emergency thermal
        if state.temperature_c >= self.config.emergency_temp_c or state.vr_temperature_c >= self.config.max_vr_temp_c:
            return {
                "reason": "emergency thermal rollback",
                "patch": self.build_patch(
                    frequency=prev_setting(
                        prev_setting(
                            state.frequency_mhz,
                            self.config.min_frequency,
                            self.config.freq_step,
                            state.frequency_options,
                            self.config.use_asic_options,
                        ),
                        self.config.min_frequency,
                        self.config.freq_step,
                        state.frequency_options,
                        self.config.use_asic_options,
                    ),
                    voltage=prev_setting(
                        prev_setting(
                            state.voltage_mv,
                            self.config.min_voltage,
                            self.config.voltage_step,
                            state.voltage_options,
                            self.config.use_asic_options,
                        ),
                        self.config.min_voltage,
                        self.config.voltage_step,
                        state.voltage_options,
                        self.config.use_asic_options,
                    ),
                    fan_percent=self.config.max_fan_percent,
                ),
            }
        
        # Low input voltage
        if state.input_voltage_mv and state.input_voltage_mv < self.config.min_input_voltage_mv:
            return {
                "reason": "input voltage too low",
                "patch": self.build_patch(
                    frequency=prev_setting(
                        state.frequency_mhz,
                        self.config.min_frequency,
                        self.config.freq_step,
                        state.frequency_options,
                        self.config.use_asic_options,
                    ),
                    voltage=prev_setting(
                        state.voltage_mv,
                        self.config.min_voltage,
                        self.config.voltage_step,
                        state.voltage_options,
                        self.config.use_asic_options,
                    ),
                    fan_percent=fan,
                ),
            }
        
        # Power limit
        if state.power_w and state.power_w > self.config.max_power_w:
            return {
                "reason": "power above configured ceiling",
                "patch": self.build_patch(
                    frequency=prev_setting(
                        state.frequency_mhz,
                        self.config.min_frequency,
                        self.config.freq_step,
                        state.frequency_options,
                        self.config.use_asic_options,
                    ),
                    fan_percent=self.config.max_fan_percent,
                ),
            }
        
        # High temperature
        if state.temperature_c >= self.config.hot_temp_c:
            return {
                "reason": "hot; cooling down",
                "patch": self.build_patch(
                    frequency=prev_setting(
                        state.frequency_mhz,
                        self.config.min_frequency,
                        self.config.freq_step,
                        state.frequency_options,
                        self.config.use_asic_options,
                    ),
                    fan_percent=self.config.max_fan_percent,
                ),
            }
        
        # Cooldown check
        if not self.can_change(state):
            return {"reason": "cooldown window active", "patch": self.build_patch(fan_percent=fan)}
        
        # Learning-based restore
        learned_restore = self.learned_restore_decision(state, fan)
        if learned_restore:
            return learned_restore
        
        # Performance climb
        climb_power_gate = self.config.max_power_w * self.config.climb_power_ratio
        if state.temperature_c <= self.config.cool_temp_c and state.power_w < climb_power_gate:
            next_freq = next_setting(
                state.frequency_mhz,
                self.config.max_frequency,
                self.config.freq_step,
                state.frequency_options,
                self.config.use_asic_options,
            )
            if self.config.learning_enabled and self.learning.is_bad_candidate(next_freq, state.voltage_mv, self.config):
                return {
                    "reason": "learning hold; next frequency candidate was previously unstable",
                    "patch": self.build_patch(fan_percent=fan)
                }
            if next_freq > state.frequency_mhz:
                return {
                    "reason": "cool and below power ceiling; raise frequency",
                    "patch": self.build_patch(frequency=next_freq, fan_percent=fan),
                }
            next_voltage = next_setting(
                state.voltage_mv,
                self.config.max_voltage,
                self.config.voltage_step,
                state.voltage_options,
                self.config.use_asic_options,
            )
            if next_voltage > state.voltage_mv and state.hashrate_gh < self.config.min_hashrate_gh:
                return {
                    "reason": "cool but below hashrate floor; raise voltage",
                    "patch": self.build_patch(voltage=next_voltage, fan_percent=fan),
                }
        
        # Temperature management
        if state.temperature_c > self.config.target_temp_c and state.frequency_mhz > self.config.min_frequency:
            return {
                "reason": "above target temp; lower frequency",
                "patch": self.build_patch(
                    frequency=prev_setting(
                        state.frequency_mhz,
                        self.config.min_frequency,
                        self.config.freq_step,
                        state.frequency_options,
                        self.config.use_asic_options,
                    ),
                    fan_percent=fan,
                ),
            }
        
        return {"reason": "hold", "patch": self.build_patch(fan_percent=fan)}
    
    def decide_ai(self, state: MinerState) -> Dict[str, Any]:
        """Make decision using AI advisor with safety guards"""
        assert self.ai is not None
        
        # Apply safety guards first
        guard = self.decide_rules(state)
        guard_reason = guard.get("reason", "")
        ai_allowed_reasons = {
            "hold",
            "cooldown window active",
            "learning hold; next frequency candidate was previously unstable",
        }
        
        # Check if safety rules allow AI decision
        if guard_reason not in ai_allowed_reasons and not guard_reason.startswith("cool and below"):
            guard["reason"] = f"safety guard before ai: {guard_reason}"
            return guard
        
        try:
            action = self.ai.decide(state, self.config, self.learning.summary(self.config))
        except Exception as exc:
            logging.warning("ai advisor failed; using local rules: %s", exc)
            self.metrics.record_error("ai_failure")
            guard["reason"] = f"ai advisor unavailable; local rules: {guard_reason}"
            return guard
        
        fan = self.desired_fan(state)
        target_fan = action.get("target_fan_percent")
        if target_fan is not None:
            fan = clamp(int(target_fan), self.config.min_fan_percent, self.config.max_fan_percent)
        
        patch = self.build_patch(fan_percent=fan)
        action_name = action.get("action", "hold")
        guardrails = guardrail_metrics(state, self.config)
        
        if action_name in {"raise_freq", "raise_voltage"} and not self.can_change(state):
            return {
                "reason": f"ai {action_name} blocked by cooldown",
                "patch": patch,
            }

        if action_name == "raise_freq":
            if not guardrails["can_climb"]:
                return {
                    "reason": "ai raise frequency blocked by climb guardrails",
                    "patch": patch,
                }
            next_freq = next_setting(
                state.frequency_mhz,
                self.config.max_frequency,
                self.config.freq_step,
                state.frequency_options,
                self.config.use_asic_options,
            )
            if self.config.learning_enabled and self.learning.is_bad_candidate(next_freq, state.voltage_mv, self.config):
                return {
                    "reason": "learning blocked ai frequency raise; candidate was previously unstable",
                    "patch": patch
                }
            patch = self.build_patch(frequency=next_freq, fan_percent=fan)
        
        elif action_name == "lower_freq":
            prev_freq = prev_setting(
                state.frequency_mhz,
                self.config.min_frequency,
                self.config.freq_step,
                state.frequency_options,
                self.config.use_asic_options,
            )
            patch = self.build_patch(frequency=prev_freq, fan_percent=fan)
        
        elif action_name == "raise_voltage":
            if not guardrails["can_climb"]:
                return {
                    "reason": "ai raise voltage blocked by climb guardrails",
                    "patch": patch,
                }
            next_voltage = next_setting(
                state.voltage_mv,
                self.config.max_voltage,
                self.config.voltage_step,
                state.voltage_options,
                self.config.use_asic_options,
            )
            patch = self.build_patch(voltage=next_voltage, fan_percent=fan)
        
        elif action_name == "lower_voltage":
            prev_voltage = prev_setting(
                state.voltage_mv,
                self.config.min_voltage,
                self.config.voltage_step,
                state.voltage_options,
                self.config.use_asic_options,
            )
            patch = self.build_patch(voltage=prev_voltage, fan_percent=fan)
        
        return {"reason": action.get("reason", "ai decision"), "patch": patch}
    
    def apply(self, decision: Dict[str, Any]) -> None:
        """Apply decision patch to the miner"""
        patch = {k: v for k, v in decision["patch"].items() if v is not None}
        
        if patch == self.last_applied:
            logging.info("no-op: %s", decision["reason"])
            return
        
        logging.info("decision=%s patch=%s", decision["reason"], patch)
        
        if self.config.dry_run:
            self.last_applied = patch
            return
        
        if patch:
            try:
                self.client.patch_system(patch)
                self.last_applied = patch
                self.successful_actions += 1
                if "frequency" in patch or "coreVoltage" in patch:
                    self.last_change_at = time.time()
            except Exception as e:
                self.metrics.record_error("apply_failure")
                raise
    
    def health_check(self) -> Dict[str, Any]:
        """Check health status of various components"""
        return {
            "status": "healthy" if self.last_error is None else "degraded",
            "last_successful_poll": self.last_state.timestamp if self.last_state else None,
            "last_error": self.last_error,
            "uptime_seconds": time.time() - self.start_time,
            "total_decisions": self.decision_count,
            "successful_actions": self.successful_actions,
            "bitaxe_reachable": self.client.health_check(),
            "state_machine_state": self.state_machine_state.name,
        }
    
    def write_status(self) -> None:
        """Write status to JSON file"""
        next_change_at = None
        if self.last_change_at:
            next_change_at = self.last_change_at + self.adaptive_cooldown_seconds(self.last_state)
        
        status = {
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "config": {
                "bitaxe_url": self.config.bitaxe_url,
                "mode": self.config.mode,
                "dry_run": self.config.dry_run,
                "loop_seconds": self.config.loop_seconds,
                "min_frequency": self.config.min_frequency,
                "max_frequency": self.config.max_frequency,
                "absolute_max_frequency": self.config.absolute_max_frequency,
                "freq_step": self.config.freq_step,
                "min_voltage": self.config.min_voltage,
                "max_voltage": self.config.max_voltage,
                "absolute_max_voltage": self.config.absolute_max_voltage,
                "voltage_step": self.config.voltage_step,
                "target_temp_c": self.config.target_temp_c,
                "hot_temp_c": self.config.hot_temp_c,
                "emergency_temp_c": self.config.emergency_temp_c,
                "absolute_max_emergency_temp_c": self.config.absolute_max_emergency_temp_c,
                "cool_temp_c": self.config.cool_temp_c,
                "max_vr_temp_c": self.config.max_vr_temp_c,
                "absolute_max_vr_temp_c": self.config.absolute_max_vr_temp_c,
                "min_input_voltage_mv": self.config.min_input_voltage_mv,
                "max_power_w": self.config.max_power_w,
                "absolute_max_power_w": self.config.absolute_max_power_w,
                "climb_power_ratio": self.config.climb_power_ratio,
                "max_error_percentage": self.config.max_error_percentage,
                "max_domain_spread_percentage": self.config.max_domain_spread_percentage,
                "critical_domain_spread_percentage": self.config.critical_domain_spread_percentage,
                "domain_spread_polls": self.config.domain_spread_polls,
                "learning_enabled": self.config.learning_enabled,
                "learning_min_samples": self.config.learning_min_samples,
                "learning_bad_limit": self.config.learning_bad_limit,
                "learning_restore_margin": self.config.learning_restore_margin,
                "learning_efficiency_weight": self.config.learning_efficiency_weight,
                "adaptive_cooldown_enabled": self.config.adaptive_cooldown_enabled,
                "adaptive_min_cooldown_seconds": self.config.adaptive_min_cooldown_seconds,
                "adaptive_max_cooldown_seconds": self.config.adaptive_max_cooldown_seconds,
                "adaptive_stable_samples": self.config.adaptive_stable_samples,
                "min_fan_percent": self.config.min_fan_percent,
                "max_fan_percent": self.config.max_fan_percent,
                "step_cooldown_seconds": self.config.step_cooldown_seconds,
                "use_asic_options": self.config.use_asic_options,
            },
            "last_applied": self.last_applied,
            "last_decision": self.last_decision,
            "last_error": self.last_error,
            "last_change_at_epoch": self.last_change_at if self.last_change_at else None,
            "next_change_at_epoch": next_change_at,
            "active_cooldown_seconds": self.adaptive_cooldown_seconds(self.last_state),
            "performance_score": performance_score(self.last_state, self.config) if self.last_state else None,
            "performance_metrics": performance_metrics(self.last_state, self.config) if self.last_state else None,
            "efficiency_gh_per_w": efficiency_gh_per_w(self.last_state) if self.last_state else None,
            "headroom": self.headroom(self.last_state) if self.last_state else None,
            "guardrails": guardrail_metrics(self.last_state, self.config) if self.last_state else None,
            "climb_power_gate_w": self.config.max_power_w * self.config.climb_power_ratio,
            "learning": self.learning.summary(self.config),
            "metrics": self.metrics.get_summary(),
            "health": self.health_check(),
            "state": asdict(self.last_state) if self.last_state else None,
        }
        
        tmp_path = f"{self.config.status_file}.tmp"
        try:
            with locked_file(tmp_path, 'w') as handle:
                json.dump(status, handle, indent=2)
            os.replace(tmp_path, self.config.status_file)
        except Exception as exc:
            logging.error("Failed to write status file: %s", exc)
    
    def run_iteration(self) -> bool:
        """Run a single iteration of the controller loop"""
        try:
            # Fetch current state
            info = self.client.get_info()
            asic = self.client.get_asic()
            state = self.parse_state(info, asic)
            self.last_state = state
            
            # Record learning data
            self.record_learning(state)
            
            # Log current state
            logging.info(
                "state temp=%.1fC vr=%.1fC freq=%sMHz volt=%smV fan=%s%% hash=%.2fGH err=%.2f%% spread=%.2f%% offline=%s power=%.2fW vin=%smV",
                state.temperature_c,
                state.vr_temperature_c,
                state.frequency_mhz,
                state.voltage_mv,
                state.fan_percent,
                state.hashrate_gh,
                state.error_percentage,
                state.domain_spread_percentage,
                state.offline_domain_count,
                state.power_w,
                state.input_voltage_mv,
            )
            
            # Update Prometheus metrics
            if self.prometheus:
                score = performance_score(state, self.config)
                self.prometheus.update_state(state, score)
            
            # Make decision
            start_time = time.time()
            decision = self.decide_ai(state) if self.config.mode == "openai" else self.decide_rules(state)
            decision_latency = time.time() - start_time
            
            # Record metrics
            self.decision_count += 1
            self.metrics.record_decision(decision.get("reason", "unknown"))
            self.metrics.record_api_latency(decision_latency)
            if self.prometheus:
                self.prometheus.record_decision(decision.get("reason", "unknown")[:50])
                self.prometheus.record_latency(decision_latency)
            
            self.last_decision = decision
            self.last_error = None
            
            # Apply decision
            self.apply(decision)
            
            return True
            
        except BitaxeConnectionError as exc:
            self.last_error = f"connection error: {exc}"
            logging.error("connection error: %s", exc)
            self.metrics.record_error("connection")
            return False
            
        except error.HTTPError as exc:
            self.last_error = f"http error: {exc}"
            logging.error("http error: %s", exc)
            self.metrics.record_error("http")
            return False
            
        except Exception as exc:
            self.last_error = f"controller error: {exc}"
            logging.exception("controller error: %s", exc)
            self.metrics.record_error("controller")
            return False
    
    def run(self) -> None:
        """Main controller loop"""
        logging.info("Starting Bitaxe controller in %s mode", self.config.mode.upper())
        if self.config.dry_run:
            logging.warning("DRY RUN MODE - no changes will be applied")
        
        while True:
            try:
                self.run_iteration()
            except Exception as e:
                logging.exception("Unhandled error in main loop: %s", e)
            
            # Write status file
            try:
                self.write_status()
            except Exception as e:
                logging.exception("failed to write status file: %s", e)
            
            # Wait for next iteration
            time.sleep(self.config.loop_seconds)


# ============================================================================
# Main Entry Point
# ============================================================================

def main() -> int:
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Guarded Bitaxe pilot")
    parser.add_argument("--once", action="store_true", help="run one iteration and exit")
    parser.add_argument("--health", action="store_true", help="run health check and exit")
    args = parser.parse_args()
    
    # Configure logging
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format="%(asctime)s %(levelname)s %(message)s",
    )
    
    try:
        # Load configuration
        config = Config.from_env()
        logging.info("Configuration loaded successfully")
        
        # Optional: Log masked config for debugging
        if log_level == "DEBUG":
            logging.debug("Config: %s", mask_sensitive_data(asdict(config)))
        
        # Create controller
        controller = Controller(config)
        
        # Health check mode
        if args.health:
            health = controller.health_check()
            print(json.dumps(health, indent=2))
            return 0 if health["status"] == "healthy" else 1
        
        # Single iteration mode
        if args.once:
            success = controller.run_iteration()
            controller.write_status()
            return 0 if success else 1
        
        # Continuous mode
        controller.run()
        
    except BitaxeConfigurationError as e:
        logging.error("Configuration error: %s", e)
        return 1
    except KeyboardInterrupt:
        logging.info("Shutting down...")
        return 0
    except Exception as e:
        logging.exception("Fatal error: %s", e)
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
