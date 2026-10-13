![Air Selangor](https://github.com/user-attachments/assets/df03fc34-f758-4c7f-9503-f4c084eb212d)

[![GitHub Repo stars](https://img.shields.io/github/stars/zubir2k/homeassistant-airselangor?style=social)](https://github.com/zubir2k/homeassistant-airselangor/stargazers)
[![hacs_badge](https://img.shields.io/badge/HACS-Default-41BDF5.svg)](https://github.com/hacs/default)
[![hacs_badge](https://img.shields.io/badge/HACS-Integration-41BDF5.svg)](https://github.com/hacs/integration)
![GitHub all releases](https://img.shields.io/badge/dynamic/json?color=41BDF5&logo=home-assistant&label=Download%20Count&suffix=%20installs&cacheSeconds=15600&url=https://analytics.home-assistant.io/custom_integrations.json&query=$.airselangor.total)
[![Buy](https://img.shields.io/badge/Belanja-Coffee-yellow.svg)](https://zubirco.de/buymecoffee)
[![GitHub Release](https://img.shields.io/github/release/zubir2k/homeassistant-airselangor.svg)](https://github.com/zubir2k/homeassistant-airselangor/releases/)

A Home Assistant custom integration for [Air Selangor](https://www.airselangor.com). Track your water bills, usage, balance and payments for every water account linked to your Air Selangor login.

## Features

- **One login, all accounts**: discovers every water account linked to your Air Selangor user
- **12 months of bills**: usage (m³) and amount (RM) per bill, as sensor attributes
- **Energy dashboard ready**: bill history is imported as long-term statistics (`airselangor:<account>_water` in m³ and `airselangor:<account>_cost` in MYR), so you can add it to the **Water** section on day one ([how it's shown](#energy-dashboard))
- **Household usage**: litres per person per day against Air Selangor's 180 L target (uses the household size set in the app)
- **Balance and payments**: outstanding balance, credit, due date, last payment
- **Re-auth flow**: if your password changes, Home Assistant asks for the new one

## Installation

### HACS (custom repository)

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=airselangor)

1. HACS → ⋮ → **Custom repositories**
2. Add `https://github.com/zubir2k/homeassistant-airselangor`, category **Integration**
3. Install **Air Selangor** and restart Home Assistant

### Manual

Copy `custom_components/airselangor/` into your Home Assistant `config/custom_components/` folder and restart.

## Configuration

**Settings → Devices & services → Add integration → Air Selangor**, then enter the login ID (IC / passport / company number) and password you use on airselangor.com. If more than one water account is linked, pick the ones to add. Change the selection later from the integration's **Configure** button.

> ⚠️ Air Selangor locks the login after 5 wrong passwords, so double-check before submitting.

## Entities (per water account)

| Entity | Unit | Notes |
|---|---|---|
| `sensor.<name>_latest_bill_usage` | m³ | Attributes: `bill_history` (12 bills), previous bill |
| `sensor.<name>_latest_bill_amount` | MYR | |
| `sensor.<name>_average_monthly_usage` | m³ | Average over the bills returned |
| `sensor.<name>_usage_per_person` | L/person/day | Attributes: household size, 180 L target, `above_target` |
| `sensor.<name>_outstanding_balance` | MYR | Attribute: payment status |
| `sensor.<name>_account_credit` | MYR | Overpayment carried forward |
| `sensor.<name>_due_date` | date | |
| `sensor.<name>_bill_date` | date | |
| `sensor.<name>_last_payment_amount` | MYR | Attributes: method, bank, reference |
| `sensor.<name>_last_payment_date` | date | |
| `sensor.<name>_account_status` | – | Diagnostic: account number, address, smart meter, e-bill |
| `binary_sensor.<name>_payment_due` | – | On when there is a balance to pay; attribute `overdue` |
| `button.<name>_refresh` | – | Diagnostic: fetch the latest data now |

Data is fetched right after you add the account (and on every Home Assistant start), then once every 24 hours. Bills are monthly, so values only change after a new bill or a payment.

For an update on demand, whatever your billing date:

- press the **Refresh** button on the account's device, or
- call the `airselangor.refresh` action (optionally with `config_entry_id` to limit it to one login), e.g. in an automation on your bill date:

```yaml
action: airselangor.refresh
```

## Energy dashboard

### Setting it up

Don't use the sensors above in the Energy dashboard. They show the *latest bill*, not a running total. Use the long-term statistics the integration imports instead:

1. **Settings → Dashboards → Energy → Water consumption → Add water source**
2. Under *Water usage*, pick **Air Selangor &lt;account&gt; water** (`airselangor:<account_number>_water`, m³).
3. Under *Cost*, choose **Use an entity tracking the total costs** and pick **Air Selangor &lt;account&gt; cost** (`airselangor:<account_number>_cost`, MYR).

The last 12 bills are imported on first setup, so the dashboard has a year of history straight away.

### How monthly bills are shown

Air Selangor reads ordinary meters **once a month**, and the portal only shows bill totals. There's no daily or hourly data, so the integration has to estimate how each bill splits across its days.

**1. Each bill is spread evenly over its billing period.** A bill covers the day after the previous bill date up to its own bill date. For example:

| Bill date | Covers | Usage | Shown per day |
|---|---|---|---|
| 21 Aug | 22 Jul – 21 Aug (31 days) | 35 m³ | 1.13 m³ |
| 21 Sep | 22 Aug – 21 Sep (31 days) | 51 m³ | 1.65 m³ |

Every day in a period gets the same value, so a busy weekend and a week away look the same. Cost is spread the same way.

**2. What each view tells you**

| View | Accuracy |
|---|---|
| Day / hour | Not meaningful. Each day's share is one flat value, recorded at 00:00 |
| Week | Total is a fair estimate, but the bars are flat |
| Month / year | Close to real. This is the view to use |

**3. Calendar months mix two bills.** Billing periods rarely start on the 1st. In the example, *August* = 1–21 Aug from the August bill (23.7 m³) + 22–31 Aug from the September bill (16.5 m³) = **40.2 m³**. No bill says 40, but over a full year the totals still add up to your bills exactly.

**4. Data is about a month behind.** Days after your latest bill date stay empty until the next bill is issued. When the daily poll (or a manual refresh) picks up the new bill, the whole period fills in at once. To catch it sooner, run `airselangor.refresh` from an automation a day or two after your usual bill date.

**5. Smart meters.** If Air Selangor fits your premises with a smart meter and starts publishing interval readings, real daily data could replace the estimate. The *Account status* sensor has a `smart_meter` attribute. Please open an issue if yours shows `true`.

## How it works

The integration talks to the same JSON API the Air Selangor web portal uses (`https://api3.airselangor.com/`):

| Purpose | Endpoint (POST) |
|---|---|
| Login | `authentication/v1/login` |
| Token refresh | `authentication/v1/refreshtoken` |
| Linked accounts | `wateraccount/v1/dashboardlist` |
| Balance, due date | `wateraccount/v1/details` |
| Bill history (type 1 = last 6, type 2 = 6 before) | `billing/v1/watertrend` |
| Household / LCD usage | `lifestyle/v1/lcd/latestbillwaterusage` |
| Payments | `payment/v1/history` |

Unauthenticated calls use a public bearer of `sha256("airselangorsecretkey" + Timestamp)`; logged-in calls use the access token. This is an unofficial integration and may break if Air Selangor changes its portal.

## Development

```bash
pip install -r requirements_test.txt ruff
ruff check . && pytest -q
```

## 📢 Disclaimer & Data Source

### Important Notice & Reliability Disclaimer

This integration retrieves account details, billing information, and water disruption notices from **Pengurusan Air Selangor Sdn Bhd (Air Selangor)** services. Please note:

* **Unofficial Integration & No Liability:** This is an independent, community-driven project and is **not affiliated with, endorsed by, or officially connected to Air Selangor**. It is provided "as is" without warranty of any kind. The maintainer assumes no legal liability for any inaccuracies, delayed status updates, billing discrepancies, or unexpected disruption notices.
* **Verify Critical Notices:** Water disruption schedules, restoration timelines, and billing statuses should always be cross-checked against official Air Selangor communication channels, including the **[Air Selangor Official Portal](https://www.airselangor.com/)**, the Air Selangor mobile app, or their official social media announcements.
* **Upstream Dependencies & Availability:** Proper functioning depends on the availability of upstream endpoints, portal changes, and local network conditions. Session timeouts, upstream schema alterations, or service downtime from Air Selangor are beyond the control of this custom component.

*By using this integration, you acknowledge and agree that the developer holds no liability for missed notices, delayed alerts, or billing discrepancies.*

## 🎖️ Credits & Acknowledgements

* Data and account service interfaces courtesy of [Air Selangor](https://www.airselangor.com/) (Pengurusan Air Selangor Sdn Bhd).
* Join the local community discussion at [Home Assistant Malaysia](https://www.facebook.com/groups/homeassistantmalaysia).
