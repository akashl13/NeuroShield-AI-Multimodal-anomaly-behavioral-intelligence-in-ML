from services.auth_service import create_session, register_user, revoke_session, validate_session


def test_registration_hashes_password_and_first_account_is_admin(db_session):
    user = register_user(db_session, "secure-analyst", "correct horse battery staple")
    assert user.role == "admin"
    assert user.password_hash != "correct horse battery staple"


def test_session_login_and_logout(db_session):
    register_user(db_session, "operator-one", "a sufficiently long password")
    user, token = create_session(db_session, "operator-one", "a sufficiently long password")
    assert user.username == "operator-one"
    assert validate_session(db_session, token).id == user.id
    revoke_session(db_session, token)
    assert validate_session(db_session, token) is None


def test_wrong_password_is_rejected(db_session):
    register_user(db_session, "operator-two", "a sufficiently long password")
    try:
        create_session(db_session, "operator-two", "wrong password")
    except ValueError as exc:
        assert "Invalid" in str(exc)
    else:
        raise AssertionError("Invalid password was accepted")