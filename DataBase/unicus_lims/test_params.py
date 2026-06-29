from dataclasses import dataclass


@dataclass
class Parameter:
    """
    Represents a single test parameter with its metadata.

    Attributes:
        name (str): The display name of the parameter (e.g. "Haemoglobin").
        unit (str): The unit of measurement (e.g. "g/dL").
        normal_range (str): A human-readable string describing the normal reference range
                            (e.g. "13.0 - 17.0").
    """
    name: str
    unit: str
    normal_range: str


# ---------------------------------------------------------------------------
# PARAM_MAP
#   Maps each test name (as stored in the database) to a list of Parameter
#   objects that describe the expected fields for that test's report.
#
#   Reference ranges are hardcoded based on standard adult values.
#   Each entry: test_name -> [Parameter, Parameter, ...]
#
#   Out-of-range detection in the PDF generator uses the normal_range string.
#   The string must follow one of these patterns:
#     - "X - Y"  (e.g. "13.0 - 17.0") for numeric range comparison
#     - Any other value will be treated as non-numeric (e.g. "Non-reactive")
#       and will not trigger out-of-range highlighting.
# ---------------------------------------------------------------------------
PARAM_MAP: dict[str, list[Parameter]] = {
    "CBC Test": [
        Parameter(name="Haemoglobin", unit="g/dL", normal_range="13.0 - 17.0"),
        Parameter(name="RBC Count", unit="million/cmm", normal_range="4.5 - 5.5"),
        Parameter(name="PCV", unit="%", normal_range="40.0 - 50.0"),
        Parameter(name="MCV", unit="fL", normal_range="80.0 - 100.0"),
        Parameter(name="MCH", unit="pg", normal_range="27.0 - 32.0"),
        Parameter(name="MCHC", unit="g/dL", normal_range="32.0 - 36.0"),
        Parameter(name="RDW", unit="%", normal_range="11.5 - 14.5"),
        Parameter(name="Total WBC Count", unit="cells/cmm", normal_range="4000 - 11000"),
        Parameter(name="Neutrophils", unit="%", normal_range="40.0 - 75.0"),
        Parameter(name="Lymphocytes", unit="%", normal_range="20.0 - 40.0"),
    ],
    "Creatinine Test": [
        Parameter(name="Creatinine", unit="mg/dL", normal_range="0.6 - 1.2"),
        Parameter(name="BUN", unit="mg/dL", normal_range="7.0 - 20.0"),
        Parameter(name="BUN/Creatinine Ratio", unit="", normal_range="6.0 - 20.0"),
        Parameter(name="eGFR", unit="mL/min/1.73m2", normal_range="> 90.0"),
    ],
    "Blood Sugar": [
        Parameter(name="Fasting Glucose", unit="mg/dL", normal_range="70.0 - 100.0"),
        Parameter(name="HbA1c", unit="%", normal_range="4.0 - 5.6"),
        Parameter(name="Postprandial Glucose", unit="mg/dL", normal_range="< 140.0"),
    ],
    "C Reactive Protein Test": [
        Parameter(name="CRP", unit="mg/L", normal_range="< 6.0"),
    ],
}
