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

---

### HTML pages and navigation

This section maps every HTML template to its URL, who can open it, and which buttons or links go where. Permission codes come from `permissions.py` and the `role_permissions` table in `db/schema.sql`.

**Entry point:** `/` redirects to `/login`.

**After login:**

- Has `dashboard.admin` → `/admin/dashboard`
- Otherwise → `/user/dashboard`

#### Page map

| Template | URL | Who can see it | Purpose |
|---|---|---|---|
| `templates/login.html` | `GET/POST /login` | Guest | Sign in |
| `templates/register.html` | `GET/POST /register` | Guest | Create account |
| `templates/user/dashboard.html` | `GET /user/dashboard` | Logged-in user | My tickets list |
| `templates/user/create_ticket.html` | `GET/POST /tickets/create` | Logged-in user | Submit new ticket |
| `templates/user/ticket_detail.html` | `GET /tickets/<id>` | Owner or staff with `tickets.view_all` | Ticket detail, remarks, staff tools |
| `templates/admin/dashboard.html` | `GET /admin/dashboard` | `dashboard.admin` | All tickets + stats |
| `templates/admin/edit_ticket.html` | `GET/POST /admin/ticket/edit/<id>` | `tickets.edit_any` | Full ticket edit form |
| `templates/admin/users.html` | `GET/POST /admin/users` | `users.manage` | Manage roles / delete users |
| `templates/admin/reports.html` | `GET /admin/reports` | `api.reports` **and** `api.tickets` | JS statistics dashboard |
| `templates/base.html` | (layout) | All pages | Navbar, flash messages, footer |
| `templates/_macros.html` | (partial) | — | Badges + attachment download links |

#### Global navbar (`templates/base.html`)

**Guest (not logged in)**

| Control | Opens |
|---|---|
| Brand / “Smart Campus” | `/login` |
| **Log in** | `/login` |
| **Register** | `/register` |

**Logged in (always visible)**

| Control | Opens |
|---|---|
| Brand | `/admin/dashboard` if `dashboard.admin`, else `/user/dashboard` |
| **My tickets** | `/user/dashboard` |
| **New ticket** | `/tickets/create` |
| **Log out** | `/logout` → clears session → `/login` |

**Logged in (permission-gated)**

| Control | Permission | Opens |
|---|---|---|
| **Admin overview** / **All tickets** | `dashboard.admin` | `/admin/dashboard` |
| **Team & roles** | `users.manage` | `/admin/users` |
| **Statistics** | `api.reports` and `api.tickets` | `/admin/reports` |

#### Per-page navigation

**`/login` — `login.html`**

| Control | Method | Goes to |
|---|---|---|
| **Log in** (submit) | POST `/login` | Success → `/admin/dashboard` or `/user/dashboard` |
| **Create one** link | GET | `/register` |

**`/register` — `register.html`**

| Control | Method | Goes to |
|---|---|---|
| **Create account** (submit) | POST `/register` | Success → `/login` |
| **Log in** link | GET | `/login` |

**`/user/dashboard` — `user/dashboard.html`**

| Control | Goes to |
|---|---|
| **New ticket** (header) | `/tickets/create` |
| Status filter (auto-submit) | Same page with `?status=...` |
| **Clear filter** | `/user/dashboard` |
| Ticket title link | `/tickets/<id>` |
| **View** button | `/tickets/<id>` |
| **Create your first ticket** (empty state) | `/tickets/create` |

**`/tickets/create` — `create_ticket.html`**

| Control | Method | Goes to |
|---|---|---|
| **Submit ticket** | POST `/tickets/create` | Success → `/tickets/<new_id>` |
| **Cancel** | GET | `/user/dashboard` |

**`/tickets/<id>` — `ticket_detail.html`**

| Control | Method | Goes to |
|---|---|---|
| **Back to my tickets** | GET | `/user/dashboard` (regular user) |
| **Back to admin overview / all tickets** | GET | `/admin/dashboard` (staff) |
| Attachment filename links | GET | `/attachments/<attachment_id>` (download) |
| **Post remark** | POST `/tickets/<id>/remark` | Same ticket page |
| **Save status & resolution** | POST `/tickets/<id>/staff-update` | Same ticket page |
| **Full edit (title, description…)** | GET | `/admin/ticket/edit/<id>` |

The staff “Manage ticket” block only appears when the user has `tickets.edit_any`.

**`/admin/dashboard` — `admin/dashboard.html`**

| Control | Goes to |
|---|---|
| **Statistics** (header) | `/admin/reports` |
| Status stat cards | `/admin/dashboard?status=<name>` |
| Status filter dropdown | Same page with `?status=...` |
| **Clear filter** | `/admin/dashboard` |
| Ticket title link | `/tickets/<id>` |
| **Edit** | `/admin/ticket/edit/<id>` (`tickets.edit_any`) |
| **Delete** | POST `/admin/ticket/delete/<id>` → `/admin/dashboard` (`tickets.delete`) |

**`/admin/ticket/edit/<id>` — `edit_ticket.html`**

| Control | Method | Goes to |
|---|---|---|
| **Back to admin overview / all tickets** | GET | `/admin/dashboard` |
| **Save changes** | POST same URL | Success → `/admin/dashboard` |
| **Cancel** | GET | `/admin/dashboard` |

**`/admin/users` — `users.html`**

| Control | Method | Goes to |
|---|---|---|
| **Back to overview** | GET | `/admin/dashboard` |
| **Save** (role change) | POST `/admin/users` | Same page |
| **Delete** | POST `/admin/users/delete/<user_id>` | Same page |

**`/admin/reports` — `reports.html`**

| Control | Goes to |
|---|---|
| **Refresh data** | Reloads via JS `fetch()` to `/api/...` (no page change) |
| Status filter | Filters API data client-side |
| **Back to admin overview / all tickets** | `/admin/dashboard` |

This page is HTML only; data comes from JSON endpoints (`/api/tickets`, `/api/reports/summary`), not new HTML pages.

#### Role → visible pages

```mermaid
flowchart TD
    subgraph guest [Guest]
        L[/login]
        R[/register]
    end

    subgraph user [User role]
        UD[/user/dashboard]
        CT[/tickets/create]
        TD[/tickets/id]
    end

    subgraph tech [Technician]
        AD[/admin/dashboard]
        TD2[/tickets/id]
        ET[/admin/ticket/edit/id]
    end

    subgraph admin [Admin]
        AD2[/admin/dashboard]
        AU[/admin/users]
        AR[/admin/reports]
        ET2[/admin/ticket/edit/id]
    end

    ROOT[/] --> L
    L -->|login user| UD
    L -->|login admin or tech| AD
    R -->|register| L

    UD --> CT
    UD --> TD
    CT -->|submit| TD
    AD --> TD2
    AD --> ET
    AD2 --> AU
    AD2 --> AR
    AD2 --> ET2
    TD2 --> ET
```

| Role | Main landing after login | Extra pages |
|---|---|---|
| **user** | `/user/dashboard` | Create ticket, own ticket detail |
| **technician** | `/admin/dashboard` | All tickets, ticket detail, inline staff update, full edit |
| **admin** | `/admin/dashboard` | Everything above plus users, statistics, delete ticket/user |

#### Permission codes (reference)

| Code | Meaning |
|---|---|
| `dashboard.admin` | Access admin/all-tickets dashboard |
| `tickets.view_all` | View any ticket (not just own) |
| `tickets.edit_any` | Update status, assignment, resolution; full edit form |
| `tickets.delete` | Delete tickets from admin dashboard |
| `users.manage` | Team & roles page; delete users |
| `api.tickets` | JSON ticket list API |
| `api.reports` | JSON reports summary API |

**Seeded role access** (from `db/schema.sql`):

- **admin** — all permissions
- **technician** — `dashboard.admin`, `tickets.view_all`, `tickets.edit_any`
- **user** — none of the above (own tickets only)
