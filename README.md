# V2Ray Proxy Auto-Collector & Tester

![GitHub Actions Workflow Status](https://github.com/Arefgh72/v2ray-proxy-pars-tester/actions/workflows/main.yml/badge.svg)

This repository automatically collects, tests, and provides reliable, up-to-date V2Ray proxy subscription links. The goal is to offer a consistent and hassle-free way to access a list of working proxies.

## 📖 About The Project

This project uses a GitHub Action that runs automatically at scheduled intervals. The process is as follows:

1.  **Fetch:** It fetches proxy configurations from a list of public V2Ray subscription links.
2.  **Test (Global):** It performs an initial test on all collected proxies from GitHub's servers (located in the US/Europe). This filters out dead or unreachable proxies.
3.  **Test (Iran-Optimized):** (Coming Soon) (It is inactive) It will send the working proxies to a dedicated server inside Iran to perform real-world latency and speed tests.
4.  **Sort & Publish:** It sorts the proxies based on performance and publishes them into several subscription links, ready for you to use.

---

## 🚀 Subscription Links

Here are the final subscription links. Simply copy the URL you want and add it to your client.

### 🌍 GitHub-Tested Proxies (Globally Accessible)

These proxies are tested from GitHub's international servers. They are generally working but may not be optimized for users inside Iran.

*   **All Active Proxies (GitHub)**
    *   Contains **all** proxies that passed the initial global test.
    > ```
    > https://raw.githubusercontent.com/Arefgh72/v2ray-proxy-pars-tester/main/output/github_all.txt
    > ```

*   **Top 500 Best Proxies (GitHub)**
    *   The top 500 fastest proxies from the global test, sorted by latency.
    > ```
    > https://raw.githubusercontent.com/Arefgh72/v2ray-proxy-pars-tester/main/output/github_top_500.txt
    > ```

*   **Top 100 Best Proxies (GitHub)**
    *   The top 100 fastest proxies from the global test. A lighter list, faster for clients to update.
    > ```
    > https://raw.githubusercontent.com/Arefgh72/v2ray-proxy-pars-tester/main/output/github_top_100.txt
    > ```

---

### 🇮🇷 Iran-Tested Proxies (Optimized for Iran) - COMING SOON (It is inactive)

These proxies will be tested from a server inside Iran for real-world performance. **These will be the recommended links for users in Iran once available.**

---

## ⚙️ How to Use

1.  **Copy** your desired subscription link from the list above.
2.  Open your V2Ray client (e.g., v2rayN, Nekoray, Streisand, etc.).
3.  Go to the "Subscriptions" or "Subscription group" section.
4.  Add a new subscription and paste the copied link.
5.  Update the subscription to fetch the proxies.

Done! Your client will now have a list of working proxies that automatically updates.

## ⚠️ Disclaimer

This service is provided as-is, with no guarantees of uptime or performance. The availability and speed of proxies can change frequently.

## 🤝 Contributing

If you have a reliable V2Ray subscription link that you'd like to add to our fetch list, please open an issue or submit a pull request to update the `config/subscriptions.txt` file.
