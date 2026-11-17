from radar.codes import classify_code, ean_valid, isbn10_valid


def test_isbn13():
    assert classify_code("9786073842839") == ("9786073842839", "ISBN13")


def test_isbn10():
    assert isbn10_valid("0306406152")
    assert classify_code("0-306-40615-2") == ("0306406152", "ISBN10")


def test_ean():
    assert ean_valid("4006381333931")
    assert classify_code("4006381333931")[1] == "EAN13"
    assert classify_code("036000291452")[1] == "UPC"


def test_invalid_ean():
    assert classify_code("9786073842838")[1] == "INVALID_CODE"


def test_internal_sku():
    assert classify_code("SKU_INTERNO")[1] == "INTERNAL_SKU"
    assert classify_code("ABC123")[1] == "INTERNAL_SKU"
    assert classify_code("SKU-INTERNO") == ("SKU-INTERNO", "INTERNAL_SKU")
    assert classify_code("")[1] == "INVALID_CODE"
