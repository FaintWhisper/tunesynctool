from typing import Optional, Dict
import re

# Constants for substitution patterns
ARTIST_FEATURES: Dict[str, str] = {
    'featuring': ' ', 'with': '',
    'feat.': '',     'feat': '',
    'ft.': '',       'ft': '',
    'prod. ': '',    'prod ': ''
}

CONJUNCTIONS: Dict[str, str] = {
    '&': 'and',
    '+': 'and'
}

BRACKETS: Dict[str, str] = {
    '[': '', ']': '',
    '(': '', ')': ''
}

PUNCTUATION: Dict[str, str] = {
    "'": '', '"': '',
    '!': '', '?': '',
    '/': ' ', '\\': ' ',
    '_': ' ', '-': ' ',
    '.': ' ', ',': '',
    ';': '', ':': '',
    '•': ' ',  # Bullet point used as separator in some music services
    '·': ' ',  # Middle dot
}

def __apply_substitutions(text: str, substitutions: Dict[str, str]) -> str:
    """
    Apply a dictionary of substitutions to the given text.
    """
    for old, new in substitutions.items():
        text = text.replace(old, new)
    return text

def __normalize_whitespace(text: str) -> str:
    """
    Removes extra whitespace by converting multiple spaces to single space.
    """
    return ' '.join(text.split())

def clean_str(s: Optional[str]) -> str:
    """
    Cleans a string by removing special characters and common industry terms.
    """
    if not s:
        return ''
    
    text = s.lower().strip()
    
    text = __apply_substitutions(text, ARTIST_FEATURES)
    text = __apply_substitutions(text, CONJUNCTIONS)
    text = __apply_substitutions(text, BRACKETS)
    text = __apply_substitutions(text, PUNCTUATION)
    
    return __normalize_whitespace(text)

def remove_parenthetical(s: Optional[str]) -> str:
    """
    Removes parenthetical content from a string (content in parentheses, brackets, etc.).
    Useful for removing remix info, featured artists, etc. from titles.
    """
    if not s:
        return ''
    
    # Remove content in parentheses and brackets
    text = re.sub(r'\([^)]*\)', '', s)
    text = re.sub(r'\[[^\]]*\]', '', text)
    
    return text.strip()

def extract_core_title(s: Optional[str]) -> str:
    """
    Extracts the core title by removing parenthetical content and trailing dashes/version info.
    """
    if not s:
        return ''
    
    # Remove parenthetical content first
    text = remove_parenthetical(s)
    
    # Remove everything after a dash followed by version/remix indicators
    # This uses a simple greedy match: everything after "- " up to a version keyword
    text = re.split(
        r'\s*-\s*.+?'  # Dash, then anything (non-greedy)
        r'\b(?:Edit|Remix|Mix|Version|Remaster|Live|Acoustic|Instrumental)\b',  # Followed by version keyword
        text,
        maxsplit=1,
        flags=re.IGNORECASE
    )[0]
    
    return text.strip()