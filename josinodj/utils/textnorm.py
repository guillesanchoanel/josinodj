"""Búsqueda tolerante: sin tildes, sin mayúsculas, sin símbolos raros.
"té" encuentra "te", "acdc" encuentra "AC/DC", y las palabras pueden ir en
cualquier orden ("pena sin" encuentra "Sin Pena")."""
import re
import unicodedata

_NON_ALNUM = re.compile(r'[^0-9a-z]+')


def norm(s: str) -> str:
    s = unicodedata.normalize('NFKD', s or '')
    s = ''.join(c for c in s if not unicodedata.combining(c))
    s = s.casefold().replace('ß', 'ss')
    return _NON_ALNUM.sub(' ', s).strip()


def haystack(*fields: str) -> str:
    """Texto donde buscar: normalizado y también todo junto sin espacios."""
    n = norm(' '.join(f or '' for f in fields))
    return n + ' | ' + n.replace(' ', '')


def matches(query: str, hay: str) -> bool:
    words = norm(query).split()
    return all(w in hay for w in words)
