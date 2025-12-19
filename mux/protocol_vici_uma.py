"""
VICI Modular Universal Actuator (UMA) – RS232 Protocol

Applies to: UMH / UMD / UMT (RS-232 variants)
Source: VICI MU Actuator Quick Start Guide v1 (09-2022)

Notes:
- ASCII commands
- CR (0x0D) terminated
- No ID used (RS-232)
- 8N1, default baud 9600
"""

CR = b"\r"


class ViciUMAProtocol:
    # ---------------------------
    # Core motion
    # ---------------------------

    @staticmethod
    def home() -> bytes:
        """HM: Move valve to position 1 (home)."""
        return b"HM" + CR

    @staticmethod
    def step_forward() -> bytes:
        """CW: Increment one position (mode 3)."""
        return b"CW" + CR

    @staticmethod
    def step_backward() -> bytes:
        """CC: Decrement one position (mode 3)."""
        return b"CC" + CR

    @staticmethod
    def goto_position(n: int) -> bytes:
        """
        GO:
        - mode 1/2: A or B
        - mode 3: absolute position nn
        """
        if isinstance(n, int):
            if n < 1:
                raise ValueError("Position must be >= 1")
            return f"GO{n}".encode() + CR
        raise TypeError("Position must be int")

    # ---------------------------
    # Position / status
    # ---------------------------

    @staticmethod
    def get_position() -> bytes:
        """CP: Query current position."""
        return b"CP" + CR

    @staticmethod
    def get_mode() -> bytes:
        """AM: Query actuator mode."""
        return b"AM" + CR

    @staticmethod
    def get_motor_type() -> bytes:
        """MA: Query motor assembly."""
        return b"MA" + CR

    @staticmethod
    def get_firmware_version(opt_board: bool = False) -> bytes:
        """VR: Query firmware version."""
        return b"VR2" + CR if opt_board else b"VR" + CR

    @staticmethod
    def help() -> bytes:
        """?: List valid commands."""
        return b"?" + CR

    # ---------------------------
    # Configuration
    # ---------------------------

    @staticmethod
    def set_mode_two_position_with_stops() -> bytes:
        return b"AM1" + CR

    @staticmethod
    def set_mode_two_position_no_stops() -> bytes:
        return b"AM2" + CR

    @staticmethod
    def set_mode_multiposition() -> bytes:
        return b"AM3" + CR

    @staticmethod
    def set_num_positions(n: int) -> bytes:
        """
        NP:
        - mode 2: number of ports
        - mode 3: number of positions
        """
        if not (1 <= n <= 99):
            raise ValueError("NP must be in range 1–99")
        return f"NP{n}".encode() + CR

    @staticmethod
    def learn_stops() -> bytes:
        """LRN: Auto-learn A/B mechanical stops."""
        return b"LRN" + CR

    @staticmethod
    def set_motor_type(motor: str) -> bytes:
        """
        MAaaa:
        motor must be 'EMH', 'EMD', or 'EMT'
        """
        motor = motor.upper()
        if motor not in ("EMH", "EMD", "EMT"):
            raise ValueError("Motor must be EMH, EMD, or EMT")
        return f"MA{motor}".encode() + CR

    # ---------------------------
    # Serial configuration
    # ---------------------------

    @staticmethod
    def get_baudrate() -> bytes:
        return b"SB" + CR

    @staticmethod
    def set_baudrate(rate: int) -> bytes:
        """
        Valid rates:
        4800, 9600, 19200, 38400, 57600, 115200
        """
        allowed = {4800, 9600, 19200, 38400, 57600, 115200}
        if rate not in allowed:
            raise ValueError(f"Invalid baudrate: {rate}")
        return f"SB{rate//100}".encode() + CR
