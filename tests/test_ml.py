from data.generate_synthetic import generate_dataset
from ml.anomaly_detection import detect_anomaly
from ml.classification import predict_risk
from ml.preprocessing import FEATURE_COLUMNS, preprocess_event, preprocess_frame
from ml.risk_engine import score_event


def test_feature_preprocessing_has_expected_numeric_schema():
    event = {"login_hour": 3, "device_was_known": False, "network_zone": "public", "location_category": "unfamiliar"}
    features = preprocess_event(event)
    assert list(features.columns) == FEATURE_COLUMNS
    assert features.loc[0, "device_known"] == 0
    assert features.loc[0, "network_zone_code"] != 0


def test_synthetic_frame_produces_finite_model_features():
    frame = generate_dataset(150, seed=123)
    features = preprocess_frame(frame)
    assert features.shape == (150, len(FEATURE_COLUMNS))
    assert features.notna().all().all()
    assert set(frame["is_anomaly"].unique()) == {0, 1}


def test_synthetic_generator_profiles_are_bounded_and_validated():
    normal = generate_dataset(100, seed=123, profile="normal")
    suspicious = generate_dataset(100, seed=123, profile="suspicious")
    assert normal["is_anomaly"].sum() == 0
    assert suspicious["is_anomaly"].sum() > 50

    try:
        generate_dataset(100, profile="unknown")
    except ValueError as exc:
        assert "Profile must be" in str(exc)
    else:
        raise AssertionError("An unsupported generation profile was accepted")


def test_isolation_forest_returns_bounded_score():
    result = detect_anomaly({"login_hour": 3, "device_was_known": False, "files_accessed": 50, "failed_login_attempts": 4})
    assert 0 <= result["score"] <= 100
    assert isinstance(result["detected"], bool)


def test_risk_score_and_classification_fallback():
    event = {"login_hour": 2, "device_was_known": False, "failed_login_attempts": 5, "files_accessed": 50, "action_count": 180, "network_bytes_mb": 900, "network_zone": "public", "location_category": "unfamiliar"}
    risk = score_event(event, anomaly_score=85)
    prediction = predict_risk(event)
    assert risk["score"] == 100
    assert risk["level"] == "CRITICAL"
    assert prediction["classification"] == "anomalous"


def test_unseen_application_adds_explainable_risk():
    risk = score_event({"application_usage": "admin_console", "network_zone": "vpn"}, baseline={"usual_applications": ["workstation", "browser"], "usual_network_zones": ["office"]})
    assert risk["factors"]["Unusual application access"] == 12
    assert risk["factors"]["Unusual network zone"] == 8