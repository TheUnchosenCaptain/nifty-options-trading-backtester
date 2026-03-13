from kiteconnect import KiteConnect

API_KEY    = "enter your key"
API_SECRET = "123abc"

def main():
    kite = KiteConnect(api_key=API_KEY)

    # 1) Get login URL, open this in browser
    login_url = kite.login_url()
    print("Go to this URL, login, and authorize:")
    print(login_url)

    print("\nAfter login, you'll be redirected to a URL like:")
    print("https://yourredirect.com/?request_token=XXXX&action=login&status=success")
    print("Copy the value of request_token and paste it here.\n")

    request_token = input("Enter request_token: ").strip()

    # 2) Exchange request_token for access_token
    data = kite.generate_session(request_token, api_secret=API_SECRET)
    access_token = data["access_token"]

    print("\n✅ Your ACCESS_TOKEN is:")
    print(access_token)
    print("\nPaste this into kite_option_downloader.py and run that script.")

if __name__ == "__main__":
    main()

