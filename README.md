# Smart Campus Ticketing System

This is a small internal ticketing site for a campus-style IT desk. People can sign up, open tickets, and attach files. Staff with the right role can pick things up, leave comments, close tickets, and pull basic reports. Behind the scenes it’s a Flask website talking to MySQL, with three kinds of accounts: regular users, technicians, and admins.

### Authors

**Bogdan Konstantinou** and **Christos Polias**.

---

### Getting going on WSL (Ubuntu)

Assume you’re on Ubuntu inside WSL and MySQL should live on the same machine. First bring the package list up to date, then install everything below in one shot—Python and its tooling, the compilers and libraries that sometimes get pulled in when pip builds wheels (including `cryptography`), Git and SSH for cloning, plus MySQL server and the `mysql` client. After that, start MySQL.

```bash
sudo apt update && sudo apt upgrade -y

sudo apt install -y \
  apt-transport-https \
  build-essential \
  ca-certificates \
  cmake \
  curl \
  default-libmysqlclient-dev \
  g++ \
  gcc \
  git \
  gnupg \
  libc6-dev \
  libbz2-dev \
  libexpat1-dev \
  libffi-dev \
  libgdbm-dev \
  liblzma-dev \
  libncurses-dev \
  libreadline-dev \
  libsqlite3-dev \
  libssl-dev \
  locales \
  make \
  mysql-client \
  mysql-server \
  openssl \
  openssh-client \
  pkg-config \
  python3 \
  python3-dev \
  python3-pip \
  python3-setuptools \
  python3-venv \
  python3-wheel \
  software-properties-common \
  tzdata \
  uuid-dev \
  wget \
  zlib1g-dev

sudo service mysql start
```

If installing Python dependencies dies inside `cryptography` and the error mentions Rust, install Rust from Ubuntu and try again:

```bash
sudo apt install -y cargo rustc
python -m pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
```

---

### Database and the built-in logins

The app doesn’t read database settings from the environment; they’re plain values at the top of `database.py`—which computer MySQL runs on, which database name to use, and which MySQL username and password to connect with. If your MySQL setup doesn’t match that yet, change the file or adjust MySQL so they line up.

When you start the app against an empty database (no tables yet), it creates the schema from `db/schema.sql`, runs a few small upgrades that are already coded in, and then adds two ready-made website accounts if they aren’t there yet: `admin@mail.com` and `service.desk@mail.com`, both with password `1234`. Those are normal rows in the `users` table, not something you hand-create in MySQL separately.

---

### Running it locally

Clone the repo, make a virtualenv, install requirements, and launch Flask:

```bash
git clone <repo-url> && cd SmartCampusTicketingSystem
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
python app.py
```

Then open a browser at http://127.0.0.1:5000 . Anything people attach to tickets lands under `uploads/ticket_files/` in the project folder.
