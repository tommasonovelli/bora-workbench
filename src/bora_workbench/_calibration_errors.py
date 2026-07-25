"""Define input and operational failure categories shared by calibration protocols."""


class CalibrationError(RuntimeError):
    """Report invalid calibration input or a failed preflight."""


class CalibrationRunError(CalibrationError):
    """Report an operational calibration failure after valid input was accepted."""
