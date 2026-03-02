# Raffle System

A premium, secure, and scalable sweepstakes platform built with **Django**, **Celery**, and **PostgreSQL**. This system enables organizers to create verified, transparent raffles with automated winner selection and integrated payment processing.

## 🚀 Key Features

- **Dual-User Ecosystem**: Dedicated dashboards for **Organizers** (to create and manage campaigns) and **Participants** (to track entries and winnings).
- **Transparent Winner Selection**: Uses verifiable hash-based seeding to ensure fairness in every draw.
- **Integrated Payments**: Seamless support for **Paystack** and **Flutterwave** for secure ticket purchases.
- **Automated Notifications**: Real-time email updates via **Celery** for entries, winner announcements, and withdrawal requests.
- **Financial Integrity**: Robust wallet system for organizers to manage revenue and for winners to withdraw prizes safely.
- **Referral System**: Built-in viral marketing tools with referral tracking and bonus ticket incentives.
- **Security First**: Hardened production configuration with support for environment-based secrets and protected database layers.

## 🛠️ Technical Stack

- **Backend**: Python, Django
- **Task Queue**: Celery, Redis
- **Frontend**: Tailwind CSS, HTML5, JavaScript
- **Storage**: Supabase (optional) or FileSystem
- **Database**: PostgreSQL (Production) / SQLite (Development)

## 📦 Installation & Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/goodyness/raffle-system.git
   cd raffle-system
   ```

2. **Create and activate a virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Environment Configuration**:
   Create a `.env` file in the root directory based on the following template:
   ```env
   DJANGO_SECRET_KEY=your_secret_key
   DJANGO_DEBUG=True
   ALLOWED_HOSTS=localhost,127.0.0.1

   # Database (Optional for Production)
   # DATABASE_URL=postgres://user:password@localhost:5432/dbname

   # Payments
   PAYSTACK_PUBLIC_KEY=your_paystack_public_key
   PAYSTACK_SECRET_KEY=your_paystack_secret_key
   FLW_PUBLIC_KEY=your_flutterwave_public_key
   FLW_SECRET_KEY=your_flutterwave_secret_key

   # Email (Brevo/SMTP)
   EMAIL_HOST=smtp-relay.brevo.com
   EMAIL_PORT=587
   EMAIL_HOST_USER=your_email
   EMAIL_HOST_PASSWORD=your_password

   # Celery / Redis
   CELERY_BROKER_URL=redis://localhost:6379/0

   # Storage (Supabase)
   SUPABASE_URL=your_supabase_url
   SUPABASE_SERVICE_ROLE_KEY=your_key
   SUPABASE_BUCKET=your_bucket
   ```

5. **Run migrations**:
   ```bash
   python manage.py migrate
   ```

6. **Start the development server**:
   ```bash
   python manage.py runserver
   ```

## 🔒 Security Note

This repository is optimized for security. The `.env` and `db.sqlite3` files are explicitly ignored to prevent secret leaks. **Never commit your `.env` file.**

## 📄 License

Distributed under the MIT License. See `LICENSE` for more information.
