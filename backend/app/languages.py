from dataclasses import dataclass


@dataclass
class LangInfo:
    code: str
    name: str
    native: str
    whisper: str
    flores: str
    mms: str


# BAIF's core operational languages in Maharashtra/MP/Gujarat/Rajasthan border regions.
SUPPORTED_LANGUAGES = {
    "en": LangInfo("en", "English", "English", "en", "eng_Latn", "eng"),
    "hi": LangInfo("hi", "Hindi", "हिन्दी", "hi", "hin_Deva", "hin"),
    "mr": LangInfo("mr", "Marathi", "मराठी", "mr", "mar_Deva", "mar"),
}


def get_language(code: str) -> LangInfo:
    return SUPPORTED_LANGUAGES.get(code, SUPPORTED_LANGUAGES["en"])


def is_supported(code: str) -> bool:
    return code in SUPPORTED_LANGUAGES


def language_options() -> list[dict]:
    return [
        {"code": info.code, "name": info.name, "native": info.native}
        for info in SUPPORTED_LANGUAGES.values()
    ]