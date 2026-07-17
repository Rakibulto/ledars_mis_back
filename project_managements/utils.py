def number_to_words(amount):
    """
    Convert a numeric amount to English words (Taka/Paisa format).
    Example: 1250.50 -> "One Thousand Two Hundred Fifty Taka and Fifty Paisa Only"
    """
    if amount is None:
        return "Zero Taka Only"

    amount = round(amount, 2)
    taka_part = int(amount)
    paisa_part = int(round((amount - taka_part) * 100))

    if taka_part == 0 and paisa_part == 0:
        return "Zero Taka Only"

    result = ""
    if taka_part > 0:
        result = f"{_number_to_words_integer(taka_part)} Taka"
    if paisa_part > 0:
        result = f"{result} and {_number_to_words_integer(paisa_part)} Paisa" if result else f"{_number_to_words_integer(paisa_part)} Paisa"
    result = f"{result} Only"

    return result


def _number_to_words_integer(n):
    """Convert an integer (0-999999999) to English words."""
    if n == 0:
        return "Zero"

    ones = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine",
            "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen",
            "Seventeen", "Eighteen", "Nineteen"]
    tens = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]

    def _convert_below_thousand(num):
        if num == 0:
            return ""
        if num < 20:
            return ones[num]
        if num < 100:
            return tens[num // 10] + (" " + ones[num % 10] if num % 10 else "")
        return ones[num // 100] + " Hundred" + (" " + _convert_below_thousand(num % 100) if num % 100 else "")

    if n < 1000:
        return _convert_below_thousand(n)

    words = ""
    crore = n // 10000000
    if crore:
        words += _convert_below_thousand(crore) + " Crore "
        n %= 10000000

    lakh = n // 100000
    if lakh:
        words += _convert_below_thousand(lakh) + " Lakh "
        n %= 100000

    thousand = n // 1000
    if thousand:
        words += _convert_below_thousand(thousand) + " Thousand "
        n %= 1000

    hundred = n // 100
    if hundred:
        words += _convert_below_thousand(hundred) + " Hundred "
        n %= 100

    if n:
        words += _convert_below_thousand(n)

    return words.strip()