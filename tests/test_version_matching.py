from tunesynctool.models import MatchPolicy, Track


def make_track(title: str, duration: int) -> Track:
    return Track(
        title=title,
        primary_artist='Version Artist',
        duration_seconds=duration,
        service_name='subsonic',
    )


def test_strict_policy_rejects_original_to_instrumental():
    source = make_track('Example Track - Original Mix', 326)
    instrumental = make_track('Example Track - Instrumental Mix', 326)

    assert not source.evaluate_match(
        instrumental,
        policy=MatchPolicy.STRICT,
    ).accepted


def test_strict_policy_rejects_radio_to_club_version():
    radio = make_track('Example Track - Producer Recut Radio Version', 166)
    club = make_track('Example Track (Producer Recut Club Version)', 298)

    assert not radio.evaluate_match(
        club,
        policy=MatchPolicy.STRICT,
    ).accepted


def test_relaxed_policy_allows_close_soft_edit_difference():
    radio = make_track('Example Track - Radio Edit', 180)
    unlabeled = make_track('Example Track', 185)

    assert not radio.evaluate_match(
        unlabeled,
        policy=MatchPolicy.STRICT,
    ).accepted
    assert radio.evaluate_match(
        unlabeled,
        policy=MatchPolicy.RELAXED,
    ).accepted


def test_relaxed_policy_still_rejects_dangerous_remix_difference():
    source = make_track('Example Track', 187)
    remix = make_track('Example Track (Guest Producer Remix)', 196)

    assert not source.evaluate_match(
        remix,
        policy=MatchPolicy.RELAXED,
    ).accepted
