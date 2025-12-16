from dataclasses import dataclass
from typing import List, Tuple
from datetime import datetime
from .gas_info import get_cas_details

STX = chr(2)
ETX = chr(3)

# --- Data Classes ---

@dataclass
class DeviceStatus:
    error: bool
    status_code: int
    status_str: str

    def as_string(self):
        return f"Device Status: {self.status_str} (code={self.status_code})"

@dataclass
class ErrorList:
    error: bool
    codes: List[str]

    def as_string(self):
        return "Active Errors: " + ", ".join(self.codes) if not self.error else "Error retrieving error list."

@dataclass
class TaskList:
    error: bool
    tasks: List[Tuple[str, str]]  # (task_id, task_name)

    def as_string(self):
        return "Task List:\n" + "\n".join(f"{tid}: {tname}" for tid, tname in self.tasks)

@dataclass
class ACONRecord:
    timestamp: int
    cas: str
    ppm: float

@dataclass
class ACONResult:
    error: bool
    records: List[ACONRecord]  # (timestamp, CAS, ppm)

    def as_string(self):
            return f"Measurement Results ({self.readable_time}):\n" + "\n".join(
                f"{get_cas_details(rec.cas)['label']}: {rec.ppm:.4f} ppm" for rec in self.records
            ) if not self.error else "Error retrieving measurement results."
    
    @property
    def timestamp(self):
        return self.records[0].timestamp if self.records else None

    @property
    def readable_time(self):
        return datetime.fromtimestamp(self.timestamp).strftime("%Y-%m-%d %H:%M:%S") if self.timestamp else None

@dataclass
class MeasurementStatus:
    error: bool
    status_code: int
    description: str

    def as_string(self):
        return f"Measurement Phase: {self.description} (code={self.status_code})"

@dataclass
class DeviceName:
    error: bool
    name: str

    def as_string(self):
        return f"Device Name: {self.name}" if not self.error else "Error retrieving device name."

@dataclass
class DeviceInfo:
    error: bool
    info: str

    def as_string(self):
        return f"Device Info: {self.info}" if not self.error else "Error retrieving device information."

@dataclass
class IterationNumber:
    error: bool
    iteration: int

    def as_string(self):
        return f"Iteration: {self.iteration}" if not self.error else "Error retrieving iteration."

@dataclass
class NetworkSettings:
    error: bool
    use_dhcp: bool
    ip: str
    netmask: str
    gateway: str

    def as_string(self):
        return f"DHCP: {self.use_dhcp}, IP: {self.ip}, Netmask: {self.netmask}, Gateway: {self.gateway}"

@dataclass
class DateTimeResult:
    error: bool
    datetime_str: str

    def as_string(self):
        if self.error:
            return "Error retrieving time."
        clean_str = self.datetime_str.replace("T", " ") # Replace 'T' with space
        return f"Device Time: {clean_str}"

@dataclass
class SelfTestResult:
    error: bool
    code: int
    description: str

    def as_string(self):
        return f"Self-Test: {self.description} (code={self.code})" if not self.error else "Error retrieving self-test result."

@dataclass
class TaskParameters:
    error: bool
    cas_list: list
    target_pressure: float
    flush_bypass: float
    flush_cell: float
    flush_cycles: int

    def as_string(self):
        if self.error:
            return "Error retrieving task parameters."
        cas_str = ", ".join(self.cas_list) if self.cas_list else "-"
        return (
            f"CAS: {cas_str} | "
            f"Target P: {self.target_pressure} mbar | "
            f"Flush Bypass: {self.flush_bypass} s | "
            f"Flush Cell: {self.flush_cell} s | "
            f"Flush Cycles: {self.flush_cycles}"
        )

@dataclass
class SystemParameter:
    name: str
    value: float
    min_val: float
    max_val: float
    unit: str

@dataclass
class SystemParameters:
    error: bool
    params: list  # List[SystemParameter]

    def as_string(self):
        if self.error:
            return "Error retrieving system parameters."
        return "System Parameters:\n" + "\n".join(
            f"{p.name}: {p.value} [{p.min_val}..{p.max_val}] {p.unit}" for p in self.params
        )

@dataclass
class InletConfig:
    id: int
    active: bool
    bypass_time: float

@dataclass
class SamplerParameters:
    error: bool
    mps_connected: bool
    inlets: list  # List[InletConfig]

    def as_string(self):
        if self.error:
            return "Error retrieving sampler parameters."
        if not self.mps_connected:
            return "MPS not connected."
        return "Inlet Configuration:\n" + "\n".join(
            f"Inlet {i.id}: {'Active' if i.active else 'Inactive'}, Bypass Time: {i.bypass_time} s"
            for i in self.inlets
        )

@dataclass
class ParameterValue:
    error: bool
    value: str

    def as_string(self):
        return f"Parameter Value: {self.value}" if not self.error else "Error retrieving parameter."

@dataclass
class GenericResponse:
    error: bool
    command: str

    def as_string(self):
        return f"{self.command} response: {'Error' if self.error else 'Success'}"

# --- Protocol Class ---

class GaseraProtocol:
    status_map = {
        0: "Initializing",
        1: "Initialization error",
        2: "Idle",
        3: "Self-test in progress",
        4: "Malfunction",
        5: "Measuring",
        6: "Calibration",
        7: "Cancelling",
        8: "Laser scan",
    }

    phase_map = {
        0: "Idle",
        1: "Gas exchange",
        2: "Integration",
        3: "Analysis",
        4: "Laser tuning"
    }

    def build_command(self, func: str, data: str = "") -> str:
        return f"{STX} {func} K0 {(data if data else '')}{ETX}"

    # Human-readable aliases
    def ask_current_status(self) -> str:
        return self.build_command("ASTS")

    def ask_active_errors(self) -> str:
        return self.build_command("AERR")

    def ask_task_list(self) -> str:
        return self.build_command("ATSK")

    def start_measurement_by_id(self, task_id: str) -> str:
        return self.build_command("STAM", task_id)

    def stop_measurement(self) -> str:
        return self.build_command("STPM")

    def get_last_measurement_results(self) -> str:
        return self.build_command("ACON")

    def set_component_order(self, cas_list: str) -> str:
        return self.build_command("SCOR", cas_list)

    def set_concentration_format(self, show_time: int, show_cas: int, show_conc: int, show_inlet: int = -1) -> str:
        fmt = f"{show_time} {show_cas} {show_conc}"
        if show_inlet in [0, 1]:
            fmt += f" {show_inlet}"
        return self.build_command("SCON", fmt)

    def get_measurement_status(self) -> str:
        return self.build_command("AMST")

    def get_device_name(self) -> str:
        return self.build_command("ANAM")

    def start_measurement_by_name(self, task_name: str) -> str:
        return self.build_command("STAT", task_name)

    def get_iteration_number(self) -> str:
        return self.build_command("AITR")

    def get_network_settings(self) -> str:
        return self.build_command("ANET")

    def set_network_settings(self, use_dhcp: int, ip: str, netmask: str, gw: str) -> str:
        return self.build_command("SNET", f"{use_dhcp} {ip} {netmask} {gw}")

    def get_device_datetime(self) -> str:
        return self.build_command("ACLK")

    def get_parameter(self, name: str) -> str:
        return self.build_command("APAR", name)

    def set_online_mode(self, enable: bool) -> str:
        return self.build_command("SONL", str(int(enable)))

    def set_laser_tuning_interval(self, interval: int) -> str:
        return self.build_command("STUN", str(interval))

    def get_task_parameters(self, task_id: int) -> str:
        return self.build_command("ATSP", str(task_id))

    def get_system_parameters(self) -> str:
        return self.build_command("ASYP")

    def get_sampler_parameters(self) -> str:
        return self.build_command("AMPS")

    def get_device_info(self) -> str:
        return self.build_command("ADEV")

    def start_self_test(self) -> str:
        return self.build_command("STST")

    def get_self_test_result(self) -> str:
        return self.build_command("ASTR")

    def reboot_device(self) -> str:
        return self.build_command("RDEV")

    # Response parsers
    def parse_response(self, response: str) -> Tuple[str, List[str]]:
        if not response.startswith(STX) or not response.endswith(ETX):
            raise ValueError("Invalid response framing")
        body = response[1:-1].strip()
        parts = body.split()
        if len(parts) < 2:
            raise ValueError("Malformed response")
        return parts[0], parts[1:]

    def parse_asts(self, response: str) -> DeviceStatus:
        cmd, parts = self.parse_response(response)
        error = parts[0] != '0'
        status_code = int(parts[1]) if len(parts) > 1 and parts[0] == '0' else -1
        return DeviceStatus(error, status_code, self.status_map.get(status_code, "Unknown"))

    def parse_aerr(self, response: str) -> ErrorList:
        cmd, parts = self.parse_response(response)
        error = parts[0] != '0'
        codes = parts[1:] if not error else []
        return ErrorList(error, codes)

    def parse_atsk(self, response: str) -> TaskList:
        cmd, parts = self.parse_response(response)
        error = parts[0] != '0'
        tasks = []
        if not error:
            i = 1
            while i < len(parts):
                task_id = parts[i]
                i += 1
                task_name = []
                while i < len(parts) and not parts[i].isdigit():
                    task_name.append(parts[i])
                    i += 1
                tasks.append((task_id, " ".join(task_name)))
        return TaskList(error, tasks)

    def parse_acon(self, response: str) -> ACONResult:
        cmd, parts = self.parse_response(response)
        error = parts[0] != '0'
        records = []
        if not error:
            i = 1
            while i + 2 < len(parts):
                timestamp = int(parts[i])
                cas = parts[i + 1]
                ppm = float(parts[i + 2])
                records.append(ACONRecord(timestamp, cas, ppm))
                i += 3
        return ACONResult(error, records)

    def parse_amst(self, response: str) -> MeasurementStatus:
        cmd, parts = self.parse_response(response)
        error = parts[0] != '0'
        code = int(parts[1]) if len(parts) > 1 and not error else -1
        return MeasurementStatus(error, code, self.phase_map.get(code, "Unknown"))

    def parse_anam(self, response: str) -> DeviceName:
        cmd, parts = self.parse_response(response)
        error = parts[0] != '0'
        name = " ".join(parts[1:]) if not error else ""
        return DeviceName(error, name)
    
    def parse_adev(self, response: str) -> DeviceInfo:
        if not response.startswith(STX) or not response.endswith(ETX):
            raise ValueError("Invalid response framing")

        import shlex
        body = response[1:-1].strip()
        tokens = shlex.split(body)  # handles quoted strings properly

        if len(tokens) < 2 or tokens[0] != "ADEV":
            raise ValueError("Malformed ADEV response")

        error = tokens[1] != '0'
        info_parts = tokens[2:] if not error else []

        info = " | ".join(part if part else "-" for part in info_parts)

        return DeviceInfo(error, info)

    def parse_aitr(self, response: str) -> IterationNumber:
        cmd, parts = self.parse_response(response)
        error = parts[0] != '0'
        iteration = int(parts[1]) if not error and len(parts) > 1 else -1
        return IterationNumber(error, iteration)

    def parse_anet(self, response: str) -> NetworkSettings:
        cmd, parts = self.parse_response(response)
        error = parts[0] != '0'
        if error or len(parts) < 5:
            return NetworkSettings(True, False, '', '', '')
        return NetworkSettings(False, parts[1] == '1', parts[2], parts[3], parts[4])

    def parse_aclk(self, response: str) -> DateTimeResult:
        cmd, parts = self.parse_response(response)
        error = parts[0] != '0'
        dt = parts[1] if not error and len(parts) > 1 else ""
        return DateTimeResult(error, dt)

    def parse_astr(self, response: str) -> SelfTestResult:
        cmd, parts = self.parse_response(response)
        error = parts[0] != '0'
        code = int(parts[1]) if len(parts) > 1 and not error else -99

        desc_map = {
            -2: "Result N/A",
            -1: "Test in progress",
             0: "Self-test failed",
             1: "Self-test passed"
        }

        description = desc_map.get(code, "Unknown")
        return SelfTestResult(error, code, description)

    def parse_atsp(self, response: str) -> TaskParameters:
        cmd, parts = self.parse_response(response)
        error = parts[0] != '0'

        if error or len(parts) < 6:
            return TaskParameters(True, [], 0.0, 0.0, 0.0, 0)

        try:
            # CAS list is comma-separated in one field
            cas_list = parts[1].split(',')
            target_pressure = float(parts[2])
            flush_bypass = float(parts[3])
            flush_cell = float(parts[4])
            flush_cycles = int(parts[5])
        except (ValueError, IndexError):
            return TaskParameters(True, [], 0.0, 0.0, 0.0, 0)

        return TaskParameters(False, cas_list, target_pressure, flush_bypass, flush_cell, flush_cycles)

    def parse_asyp(self, response: str) -> SystemParameters:
        cmd, parts = self.parse_response(response)
        error = parts[0] != '0'

        params = []

        if error or len(parts) < 2:
            return SystemParameters(True, [])

        for part in parts[1:]:
            tokens = part.split(',')
            if len(tokens) != 5:
                continue
            try:
                name = tokens[0]
                value = float(tokens[1])
                min_val = float(tokens[2])
                max_val = float(tokens[3])
                unit = tokens[4]
                params.append(SystemParameter(name, value, min_val, max_val, unit))
            except ValueError:
                continue  # skip malformed entry

        return SystemParameters(False, params)

    def parse_amps(self, response: str) -> SamplerParameters:
        cmd, parts = self.parse_response(response)

        if not parts:
            return SamplerParameters(True, False, [])

        status = parts[0]
        if status == '1':
            return SamplerParameters(True, False, [])
        elif status == '2':
            return SamplerParameters(False, False, [])  # MPS not connected

        inlets = []
        try:
            i = 1
            while i + 2 < len(parts):
                inlet_id = int(parts[i])
                active = parts[i + 1] == '1'
                bypass_time = float(parts[i + 2])
                inlets.append(InletConfig(inlet_id, active, bypass_time))
                i += 3
        except ValueError:
            return SamplerParameters(True, False, [])

        return SamplerParameters(False, True, inlets)

    def parse_apar(self, response: str) -> ParameterValue:
        cmd, parts = self.parse_response(response)
        error = parts[0] != '0'
        value = parts[1] if not error and len(parts) > 1 else ""
        return ParameterValue(error, value)

    def parse_generic(self, response: str, command: str) -> GenericResponse:
        cmd, parts = self.parse_response(response)
        return GenericResponse(error=(parts[0] != '0'), command=command)
