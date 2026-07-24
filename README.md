# tunesynctool (formerly Navify)

A Python package and CLI* to transfer music between your local/commercial streaming services. Supports track matching.

*Under development

Tunesynctool supports the following services:

- Spotify (official API)
- Spotify public playlists (read-only source; no API credentials required)
- Deezer (optional dependency)
- Any Subsonic-like service (Navidrome, Airsonic, etc.)
- YouTube Music

Support for other services will be added in the future.

## Project relationship and maintenance policy

This repository is a community-maintained fork of [WilliamNT/tunesynctool](https://github.com/WilliamNT/tunesynctool). The original repository remains the upstream project and the source of the broader project direction, authorship, and history.

This fork exists to preserve useful matching and playlist-sync improvements and to provide a maintenance bridge for people already relying on them while equivalent changes are evaluated for contribution upstream. It is not presented as a replacement for, or an official continuation of, the upstream project.

### Matching policy

Both `transfer` and `sync` accept
`--match-policy [strict|relaxed]`:

- `strict` is the default. It requires compatible recording/version metadata
  and strongly favors matching duration. It rejects conflicting remixes,
  live/acoustic/instrumental versions, sped/slowed recordings, and large
  duration differences.
- `relaxed` is opt-in. It widens the duration allowance only when a
  recognized soft label such as radio, edit, clean, or explicit explains the
  difference. It still rejects the dangerous version families above,
  conflicting named versions, intros, and excessive differences between
  otherwise unlabeled recordings.

For example:

```shell
tunesynctool transfer --from spotify --to subsonic \
  --match-policy strict "<playlist-id>" --preview
```

## Track Matching Benchmark

This fork was compared with
[upstream commit `7035a4f9b2e12021b7f4a088fb8a3ea610675d37`](https://github.com/WilliamNT/tunesynctool/commit/7035a4f9b2e12021b7f4a088fb8a3ea610675d37).
Both matchers received the same tracks and search results. Matches were
checked using title, artist, album, and duration.

| Aggregate result | This fork | Upstream |
|---|---:|---:|
| Present tracks matched | 204/217 (94.0%) | 196/217 (90.3%) |
| Absent tracks incorrectly matched | 0/149 (0.0%) | 10/149 (6.7%) |
| Strict review: correct matches | 50/50 | 25/50 |
| Strict review: incorrect matches | 0 | 7 |
| Strict review: correct tracks missed | 0 | 18 |
| Relaxed review: correct matches | 51/51 | 25/51 |
| Relaxed review: incorrect matches | 0 | 7 |
| Relaxed review: correct tracks missed | 0 | 19 |

## Usage

Install the fork-specific version directly from GitHub:

```shell
pip install git+https://github.com/FaintWhisper/tunesynctool.git
```

The standard installation supports Spotify, credential-free public Spotify
playlists, Subsonic-compatible services, and YouTube Music without installing
`streamrip` or Pillow.

Deezer support is optional. Install the fork with its `deezer` extra when you need it:

```shell
pip install "tunesynctool[deezer] @ git+https://github.com/FaintWhisper/tunesynctool.git"
```

The current Deezer driver is read-only: it can be used as a source, but not as
the target of `transfer` or `sync`.

Reading public Spotify playlists without Spotify API credentials is included
in the standard installation; no extra is required. For an editable
development checkout, use `pip install -e .`, or
`pip install -e ".[deezer]"` to include Deezer.

This fork requires Python 3.11 or newer. The base package is checked against
Python 3.11 through 3.14. Deezer is checked separately on Python 3.11 through
3.13 because the current `streamrip` release restricts Pillow to versions that
do not provide Python 3.14 wheels. Until that restriction is resolved upstream,
use Python 3.13 or earlier if you need Deezer.

The standard installation, including `spotifyscraper`, is checked against
Python 3.11 through 3.14. However, `spotifyscraper` currently advertises
Python 3.10 through 3.13 in its classifiers, so Python 3.14 compatibility
should be considered best-effort until it is explicitly supported upstream.

### Public Spotify playlists without API credentials

The `spotify-public` provider reads public Spotify playlists without a client
ID or client secret. It is included in the standard installation and can be
used as the source of a transfer:

```shell
tunesynctool transfer --from spotify-public --to subsonic \
  "https://open.spotify.com/playlist/<public-playlist-id>" --preview
```

It supports public playlists only and cannot be used as a transfer destination
or with `sync`. Use the regular `spotify` provider for private playlists or
Spotify write and search features.

## Configuration

Configuration options can be loaded from the environment or be manually specified in code. [Check the upstream documentation](https://github.com/WilliamNT/tunesynctool/wiki/Configuration) for more information.

# FAQ

## Is there a way to use tunesynctool from the CLI?
Yes, see the upstream wiki.

## Does this package offer functionality to download or stream music?
**No**, use the official clients for that.

## How does matching work?

Learn more about the original matching design in the [upstream matching documentation](https://github.com/WilliamNT/tunesynctool/wiki/Track-matching).
The fork ranks all retrieved candidates instead of accepting the first
threshold hit. Duration carries 30% of available weighted evidence, while
release year carries only 1%; missing fields are excluded rather than counted
as matches or mismatches. Strong service IDs, ISRCs, and MusicBrainz recording
IDs remain authoritative.
