# v2ray-proxy-pars-tester

# V2Ray Proxy Auto-Collector & Tester

![GitHub Actions Workflow Status](https://github.com/Arefgh72/v2ray-proxy-pars-tester/actions/workflows/v2ray_proxy_tester.yml/badge.svg)

This repository automatically collects, tests, and provides reliable, up-to-date V2Ray proxy subscription links. The goal is to offer a consistent and hassle-free way to access a list of working proxies.

## 📖 About The Project

This project uses a GitHub Action that runs automatically at scheduled intervals (e.g., every hour). The process is as follows:

1.  **Fetch:** It fetches proxy configurations from a list of public V2Ray subscription links.
2.  **Test (Global):** It performs an initial test on all collected proxies from GitHub's servers (located in the US/Europe). This filters out dead or unreachable proxies.
3.  **Test (Iran-Optimized):** It sends the working proxies to a dedicated server inside Iran to perform real-world latency and speed tests. This determines which proxies are truly fast and usable from within Iran.
4.  **Sort & Publish:** It sorts the proxies based on performance and publishes them into several subscription links, ready for you to use.

---

## 🚀 Subscription Links

Here are the final subscription links. Choose the one that best fits your needs.

**Important:** Click on the link you want, then click the **"Raw"** button on the GitHub page to get the direct subscription link, or simply copy the URL below.

### 🌍 GitHub-Tested Proxies (Globally Accessible)

These proxies are tested from GitHub's international servers. They are generally working but may not be optimized for users inside Iran.

*   **All Active Proxies (GitHub)**
    *   Contains **all** proxies that passed the initial global test. A larger list, but with variable speeds.
    > ```
    > https://raw.githubusercontent.com/Arefgh72/v2ray-proxy-pars-tester/main/output/github_all_active_proxies.txt
    > ```

*   **Top 500 Best Proxies (GitHub)**
    *   The top 500 fastest proxies from the global test, sorted by latency. A good balance of quantity and performance.
    > ```
    > https://raw.githubusercontent.com/Arefgh72/v2ray-proxy-pars-tester/main/output/github_best_500_proxies.txt
    > ```

*   **Top 100 Best Proxies (GitHub)**
    *   The top 100 fastest proxies from the global test. A lighter list, faster for clients to update.
    > ```
    > https://raw.githubusercontent.com/Arefgh72/v2ray-proxy-pars-tester/main/output/github_best_100_proxies.txt
    > ```

---

### 🇮🇷 Iran-Tested Proxies (Optimized for Iran)

These proxies are tested from a server inside Iran for real-world performance. **These are the recommended links for users in Iran.**

*   **Top 500 Best Proxies (Iran)**
    *   The top 500 proxies with the best combination of low latency and high speed when tested from Iran.
    > ```
    > https://raw.githubusercontent.com/Arefgh72/v2ray-proxy-pars-tester/main/output/iran_best_500_proxies.txt
    > ```

*   **Top 100 Best Proxies (Iran)**
    *   The top 100 fastest and most stable proxies for Iran. **Recommended for most users** as it's lightweight and reliable.
    > ```
    > https://raw.githubusercontent.com/Arefgh72/v2ray-proxy-pars-tester/main/output/iran_best_100_proxies.txt
    > ```

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

If you have a reliable V2Ray subscription link that you'd like to add to our fetch list, please open an issue or submit a pull request to update the `config/subscription_links.txt` file.
