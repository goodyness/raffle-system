# Raffle System: Comprehensive Overview & Technical Detail

Welcome to the **Raffle System**. This document provides an extensive, in-depth explanation of what the platform is, how it works, how you can use it, and why it's the most secure and fair digital campaign tool available.

---

## 1. System Overview

The Raffle System is a modern, high-tier web application designed to digitize and manage raffles, giveaways, and sweepstakes. Unlike traditional giveaways where a host may manually select a winner (often leading to doubts about fairness), this platform acts as an **escrow and automated mediator**. 

### How it operates mathematically:
- **Organizers (Hosts)** create campaigns (raffles) setting a specific ticket price and total tickets available to reach a target payout.
- **Participants** buy tickets. Their money does *not* go directly to the organizer. It goes into the platform’s secure **Payout Pool**.
- **The Draw**: When the campaign ends, the system algorithmically draws a winner (or multiple winners).
- **The Settlement**: The money pooled is immediately split—the winners receive the advertised prize (or cash equivalent), and the organizer receives their net earnings. Neither party has to chase each other for payment; the system settles it all instantly.

---

## 2. Core Stakeholders & Getting Started

### Roles inside the System
There are three fundamental types of users:
1. **Grand Admins**: The platform owners. They oversee the entire ecosystem, handling disputes, monitoring system revenue, and approving bank withdrawals.
2. **Organizers (Partners)**: Individuals or brands hosting the raffles.
3. **Participants**: Users who buy tickets to enter raffles.

### Setting Up a Profile
Setting up your profile allows you to participate in the ecosystem fully:
1. **Registration**: Go to the website and choose either "Register as Organizer" or "Register as Participant". You will provide an email address and a secure password.
2. **Verification**: To prevent spam and fake accounts, the system enforces a strict OTP (One-Time Password) verification sent directly to your email. You have 5 attempts to enter this correctly before you are locked out to prevent brute-force attacks.
3. **Settings**: Once logged in, navigate to `Profile Settings`. Here, you can:
    - Update your Full Name and Phone Number.
    - Change your password.
    - **(Organizers Only)** Add your Bank Details (Bank Name, Account Name, Account Number) which are saved for future withdrawals.

### Setting Up a Raffle (For Organizers)
Once an Organizer is verified, launching a campaign is seamless:
1. Go to your **Organizer Dashboard**.
2. Click **Create New Raffle**.
3. Fill in the campaign parameters:
    - **Title & Description**: What are you raffling off?
    - **Ticket Price**: The cost per entry (e.g., ₦1,000).
    - **Target Participants**: How many tickets must be sold.
    - **Number of Winners**: How many people will win a prize.
    - **Payout Percentage**: How much of the total pool goes to the winner(s). (The system enforces a strict minimum of 75% to ensure participants are fairly rewarded).
    - **End Date & Time**: When the raffle will close.
4. Upload a high-quality cover image and launch!

---

## 3. How Secure is It?

We built this system mirroring financial-grade applications. It acts as an escrow, so security is our absolute highest priority.

### Financial Integrity & Atomic Blocks
The system handles user money. When a participant buys a ticket, or when a raffle concludes, multiple database entries must update (e.g., debit participant, credit raffle pool, increment ticket count).
- **Atomic Transactions**: We use database-level `transaction.atomic()` blocks. This means if *any* part of a payment process fails (e.g., the internet cuts out midway), the entire transaction rolls back. A user's money cannot disappear into the void. It either 100% succeeds, or 100% fails.

### Race Condition Protection
What happens if two users try to buy the last remaining ticket at the exact same millisecond? Or if an organizer clicks "Withdraw" twice very fast?
- **Row-level Locking**: We use `select_for_update()` on financial rows. The system locks the user's wallet table while calculating the withdrawal. If a second request comes in, it is forced to wait in line until the first request finishes, entirely preventing double-spending or negative balances.

### Threat Mitigation
1. **Brute-Force Attacks**: Hackers cannot guess your OTP or guess your password infinitely. The system tracks failed attempts and locks the flow after 5 tries.
2. **Data Leakage Check**: Organizer Dashboards and Participant Dashboards are strictly walled off. User A can never accidentally access User B’s wallet or ticket history.
3. **Pending Withdrawal Limits**: Organizers and Participants can only have *one* pending withdrawal at a time. You cannot spam the Admins with 50 withdrawal requests.

---

## 4. How Fair is It?

The primary value proposition of the Raffle System is **Trustless Fairness**. 

In traditional Instagram or physical giveaways, the host can cheat. They can pick a friend, or fake the draw. **On this platform, the Organizer has ZERO control over the draw.**

### 1. Completely Automated Draws
When a raffle's timer expires, the organizer does not click a button to pick a winner. A background server worker (Celery) automatically wakes up, locks the raffle, and executes the algorithm.

### 2. Fair Algorithmic Selection
The system pools every single valid, paid ticket into an array. It then uses Python's `random.choice()`—seeded against system entropy—to blindly pull the winning ticket(s) from that array. Because the execution runs on the secure server backend:
- The Organizer cannot influence the randomizer.
- The Admin cannot influence the randomizer.
- Participants have a mathematically provable, equal chance of winning based exclusively on the number of tickets they hold.

### 3. Immediate Settlement
The moment the algorithm picks the winner, the money is physically moved out of the system's "Holding Pool":
- The Winner(s) have the advertised prize money added to their Withdrawable Balance.
- The Organizer gets their commission (the remainder) added to their Withdrawable Balance.
There is no "waiting for the host to pay out." The system escrows the funds from the start, guaranteeing the winner gets paid instantly.

### 4. Transparent Earnings
Organizers see exactly what happens to the money. The dashboard provides a complete breakdown:
- Total Revenue Collected
- Total Payout to Winners
- Organizer's Share
- System's Share
Everything equals 100%. No hidden fees exist outside of the clearly stated withdrawal processing fee (₦100) and ticket processing fee.

---

## Summary

The **Raffle System** takes the chaos and uncertainty out of giveaways. 
- For **Users**, it guarantees their entry is fairly counted and their winnings are instantly secured in their wallet.
- For **Organizers**, it gives them a professional, beautiful platform to monetize their audience without having to deal with the logistics of collecting money, writing down names, or proving they didn't cheat. 

The system handles the money, the math, and the security seamlessly.
