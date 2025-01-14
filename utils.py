# utils.py

def remove_amp(text: str) -> str:
    """
    Удаляет все вхождения 'amp;' из строки, чтобы избежать проблем
    с символом амперсанда в XML.
    """
    return text.replace("amp;", "")
