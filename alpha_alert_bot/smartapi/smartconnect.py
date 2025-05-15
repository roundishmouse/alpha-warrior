def start_websocket():
    print("Running Alpha Warrior with SmartAPI + TOTP...")

    api_key = os.environ.get("SMARTAPI_API_KEY")
    client_code = os.environ.get("SMARTAPI_CLIENT_CODE")
    pin = os.environ.get("SMARTAPI_PIN")
    totp_secret = os.environ.get("SMARTAPI_TOTP")

    # Generate TOTP dynamically
    totp = pyotp.TOTP(totp_secret).now()

    try:
        obj = SmartConnect()
        data = obj.generateSession(api_key=api_key, client_code=client_code, password=pin, totp=totp)
        jwtToken = obj.jwt_token
        print("Login successful. JWT:", jwtToken)
    except Exception as e:
        print("Login failed:", e)
        return

    from nse_token_data import nse_tokens
    symbols = get_top_stocks(nse_tokens, obj)

    is_fallback = len(symbols) == 0 or len(symbols[0]) == 0

    message = f"<b>{'Relaxed' if is_fallback else 'Quant'} Picks {datetime.now().strftime('%d-%b-%Y')}:</b>\n"
    message += f"Scanned: {len(nse_tokens)} | Selected: {len(symbols)}\n\n"

    for i, stock in enumerate(symbols, start=1):
        symbol, token, ltp = stock[:3]
        message += f"<b>#{i} {symbol}</b>\nLTP: {ltp}\n"
        if not is_fallback:
            message += f"Score: {round(stock[3], 2)}\n"
        message += "\n"

    send_telegram(message)
