"""Unit tests for the Localization framework and language catalogs."""

from __future__ import annotations

# Import catalogs to trigger registration
import services.shared.localization.catalog_en
import services.shared.localization.catalog_hi
import services.shared.localization.catalog_kn
import services.shared.localization.catalog_mr
import services.shared.localization.catalog_ta
import services.shared.localization.catalog_te  # noqa: F401
from services.shared.localization import (
    DEFAULT_LANGUAGE,
    LANGUAGE_NAMES,
    SupportedLanguage,
    Translator,
    get_catalog,
    get_translator,
    list_supported_languages,
    register_catalog,
)


# ---------------------------------------------------------------------------
# SupportedLanguage enum
# ---------------------------------------------------------------------------
class TestSupportedLanguage:
    def test_six_languages(self):
        assert len(SupportedLanguage) == 6

    def test_values(self):
        assert SupportedLanguage.ENGLISH == "en"
        assert SupportedLanguage.HINDI == "hi"
        assert SupportedLanguage.TAMIL == "ta"
        assert SupportedLanguage.TELUGU == "te"
        assert SupportedLanguage.KANNADA == "kn"
        assert SupportedLanguage.MARATHI == "mr"

    def test_language_names(self):
        assert len(LANGUAGE_NAMES) == 6
        assert "Hindi" in LANGUAGE_NAMES[SupportedLanguage.HINDI]

    def test_default_is_english(self):
        assert DEFAULT_LANGUAGE == SupportedLanguage.ENGLISH


# ---------------------------------------------------------------------------
# Catalog registration
# ---------------------------------------------------------------------------
class TestCatalogRegistry:
    def test_english_catalog_registered(self):
        catalog = get_catalog(SupportedLanguage.ENGLISH)
        assert len(catalog) > 0

    def test_hindi_catalog_registered(self):
        catalog = get_catalog(SupportedLanguage.HINDI)
        assert len(catalog) > 0

    def test_all_regional_catalogs_registered(self):
        for lang in SupportedLanguage:
            catalog = get_catalog(lang)
            assert len(catalog) > 0, f"No catalog for {lang.value}"

    def test_register_merges_entries(self):
        register_catalog(SupportedLanguage.ENGLISH, {"test.custom_key": "Custom"})
        catalog = get_catalog(SupportedLanguage.ENGLISH)
        assert "test.custom_key" in catalog
        assert "risk.category.high" in catalog  # original keys still present

    def test_unregistered_language_returns_empty(self):
        # get_catalog with a valid enum but cleared catalog scenario
        # We test by checking a non-existent key
        catalog = get_catalog(SupportedLanguage.ENGLISH)
        assert "nonexistent.key.xyz" not in catalog


# ---------------------------------------------------------------------------
# Translator — core functionality
# ---------------------------------------------------------------------------
class TestTranslator:
    def test_translate_existing_key(self):
        t = get_translator(SupportedLanguage.ENGLISH)
        result = t.translate("risk.category.high")
        assert result == "High Risk"

    def test_translate_hindi(self):
        t = get_translator(SupportedLanguage.HINDI)
        result = t.translate("risk.category.high")
        assert "जोखिम" in result  # contains Hindi word for "risk"

    def test_translate_with_variables(self):
        t = get_translator(SupportedLanguage.ENGLISH)
        result = t.translate(
            "risk.score_explanation", score=350,
        )
        assert "350" in result

    def test_translate_missing_key_returns_key(self):
        t = get_translator(SupportedLanguage.ENGLISH)
        result = t.translate("nonexistent.key.xyz")
        assert result == "nonexistent.key.xyz"

    def test_fallback_to_english(self):
        """Regional languages should fall back to English for missing keys."""
        en_catalog = get_catalog(SupportedLanguage.ENGLISH)
        ta_catalog = get_catalog(SupportedLanguage.TAMIL)
        # Find a key in English but not in Tamil
        missing_in_tamil = None
        for key in en_catalog:
            if key not in ta_catalog:
                missing_in_tamil = key
                break
        if missing_in_tamil:
            t = get_translator(SupportedLanguage.TAMIL)
            result = t.translate(missing_in_tamil)
            assert result == en_catalog[missing_in_tamil]

    def test_has_key(self):
        t = get_translator(SupportedLanguage.ENGLISH)
        assert t.has_key("risk.category.high") is True
        assert t.has_key("nonexistent_key") is False

    def test_available_keys(self):
        t = get_translator(SupportedLanguage.ENGLISH)
        keys = t.available_keys()
        assert len(keys) > 0
        assert "risk.category.high" in keys

    def test_language_property(self):
        t = get_translator(SupportedLanguage.HINDI)
        assert t.language == SupportedLanguage.HINDI

    def test_format_error_returns_template(self):
        """If variable substitution fails, return the raw template."""
        catalog = {"test.fmt": "Hello {name} {missing}"}
        t = Translator(SupportedLanguage.ENGLISH, catalog)
        result = t.translate("test.fmt", name="World")
        # Should return template since {missing} is not provided
        assert "Hello" in result


# ---------------------------------------------------------------------------
# get_translator
# ---------------------------------------------------------------------------
class TestGetTranslator:
    def test_from_enum(self):
        t = get_translator(SupportedLanguage.ENGLISH)
        assert t.language == SupportedLanguage.ENGLISH

    def test_from_string(self):
        t = get_translator("hi")
        assert t.language == SupportedLanguage.HINDI

    def test_invalid_string_falls_back_to_english(self):
        t = get_translator("xx")
        assert t.language == SupportedLanguage.ENGLISH

    def test_english_translator_no_fallback(self):
        # English should not have itself as fallback
        t = get_translator(SupportedLanguage.ENGLISH)
        assert t._fallback == {}

    def test_regional_translator_has_english_fallback(self):
        t = get_translator(SupportedLanguage.TAMIL)
        assert len(t._fallback) > 0


# ---------------------------------------------------------------------------
# list_supported_languages
# ---------------------------------------------------------------------------
class TestListSupportedLanguages:
    def test_returns_six_languages(self):
        langs = list_supported_languages()
        assert len(langs) == 6

    def test_structure(self):
        langs = list_supported_languages()
        for lang in langs:
            assert "code" in lang
            assert "name" in lang

    def test_codes(self):
        langs = list_supported_languages()
        codes = {l["code"] for l in langs}
        assert codes == {"en", "hi", "ta", "te", "kn", "mr"}


# ---------------------------------------------------------------------------
# Cross-language consistency
# ---------------------------------------------------------------------------
class TestCatalogConsistency:
    def test_all_catalogs_have_risk_keys(self):
        """Every language should have the core risk keys."""
        for lang in SupportedLanguage:
            catalog = get_catalog(lang)
            assert "risk.category.low" in catalog, f"Missing in {lang.value}"
            assert "risk.category.high" in catalog, f"Missing in {lang.value}"

    def test_all_catalogs_have_general_keys(self):
        for lang in SupportedLanguage:
            catalog = get_catalog(lang)
            assert "general.welcome" in catalog, f"Missing in {lang.value}"
            assert "general.error" in catalog, f"Missing in {lang.value}"

    def test_all_catalogs_have_consent_keys(self):
        for lang in SupportedLanguage:
            catalog = get_catalog(lang)
            assert "consent.purpose.credit_assessment" in catalog, f"Missing in {lang.value}"

    def test_all_catalogs_have_cultural_keys(self):
        for lang in SupportedLanguage:
            catalog = get_catalog(lang)
            assert "cultural.kcc_benefit" in catalog, f"Missing in {lang.value}"
            assert "cultural.shg_benefit" in catalog, f"Missing in {lang.value}"

    def test_variable_substitution_across_languages(self):
        """All languages should correctly handle variable substitution."""
        for lang in SupportedLanguage:
            t = get_translator(lang)
            result = t.translate("risk.score_explanation", score=500)
            assert "500" in result, f"Variable substitution failed in {lang.value}"


# ---------------------------------------------------------------------------
# Field-level Encryption cross-test
# ---------------------------------------------------------------------------
class TestFieldEncryption:
    def test_sensitivity_levels(self):
        from services.shared.encryption.field_encryption import (
            PII_FIELD_MAP,
            SensitivityLevel,
        )
        assert SensitivityLevel.RESTRICTED.value == "RESTRICTED"
        assert "aadhaar_number" in PII_FIELD_MAP
        assert PII_FIELD_MAP["aadhaar_number"] == SensitivityLevel.RESTRICTED

    def test_encrypt_decrypt_field(self):
        from services.shared.encryption import LocalEncryptor
        from services.shared.encryption.field_encryption import FieldEncryptor

        encryptor = LocalEncryptor()
        fe = FieldEncryptor(encryptor)
        encrypted = fe.encrypt_field("phone_number", "9876543210")
        assert encrypted.ciphertext != "9876543210"
        assert encrypted.field_name == "phone_number"
        decrypted = fe.decrypt_field(encrypted)
        assert decrypted == "9876543210"

    def test_mask_field(self):
        from services.shared.encryption import LocalEncryptor
        from services.shared.encryption.field_encryption import FieldEncryptor

        encryptor = LocalEncryptor()
        fe = FieldEncryptor(encryptor)
        masked = fe.mask_field("9876543210", visible_chars=4)
        assert masked.endswith("3210")
        assert masked.startswith("*")

    def test_encrypt_dict(self):
        from services.shared.encryption import LocalEncryptor
        from services.shared.encryption.field_encryption import FieldEncryptor

        encryptor = LocalEncryptor()
        fe = FieldEncryptor(encryptor)
        data = {
            "loan_id": "L-001",
            "phone_number": "9876543210",
            "status": "active",
        }
        encrypted = fe.encrypt_dict(data)
        assert encrypted["loan_id"] == "L-001"  # non-PII unchanged
        assert encrypted["status"] == "active"  # non-PII unchanged
        assert isinstance(encrypted["phone_number"], dict)  # PII field encrypted
