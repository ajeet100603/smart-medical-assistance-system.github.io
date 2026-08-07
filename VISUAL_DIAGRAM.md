# 🎨 Visual Diagram - तीन Pages कैसे काम करते हैं

## Architecture Diagram:

```
                    ┌─────────────────────────┐
                    │  Smart Medical System   │
                    │   localhost:5000/       │
                    └────────────┬────────────┘
                                 │
                    ┌────────────┴────────────┐
                    │  Role Selector Page     │
                    │  (Home Page)            │
                    └────────────┬────────────┘
                                 │
                  ┌──────────────┼──────────────┐
                  │              │              │
                  ▼              ▼              ▼
            ┌──────────┐   ┌──────────┐   ┌──────────┐
            │ PATIENT  │   │ HOSPITAL │   │  ADMIN   │
            │  LOGIN   │   │  LOGIN   │   │  LOGIN   │
            └────┬─────┘   └────┬─────┘   └────┬─────┘
                 │              │              │
                 ▼              ▼              ▼
            ┌──────────┐   ┌──────────┐   ┌──────────┐
            │ 🟢 GREEN │   │ 🔵 BLUE  │   │ 🟣 PURPLE│
            │  PANEL   │   │ PANEL    │   │ PANEL    │
            └──────────┘   └──────────┘   └──────────┘
```

---

## Page Flow:

### **PATIENT (GREEN) 🟢**

```
Home Page
   ↓
"I'm a Patient" Button Click
   ↓
/patient/login Page (Green Alert)
   ↓
Enter Aadhaar + Email
   ↓
/patient/panel (Green Navbar)
├─ 📊 Dashboard
├─ 🔍 Search Disease
├─ 👤 Account
└─ (Hospital/Admin options नहीं)
```

### **HOSPITAL (BLUE) 🔵**

```
Home Page
   ↓
"I'm a Hospital" Button Click
   ↓
/hospital/login Page (Blue Alert)
   ↓
Enter Email + Password
   ↓
/hospital/dashboard (Blue Navbar)
├─ 📊 Dashboard
├─ 📄 Requests & Cases
├─ 👤 Account
└─ (Patient/Admin options नहीं)
```

### **ADMIN (PURPLE) 🟣**

```
Home Page
   ↓
"I'm an Admin" Button Click
   ↓
/admin/login Page (Purple Alert)
   ↓
Enter Username + Password
   ↓
/admin/dashboard (Purple Navbar)
├─ 📊 Dashboard
├─ 🏥 Hospital Management
├─ 💊 Disease Management
├─ 📋 Claims Management
├─ 👤 Account
└─ (Patient/Hospital options नहीं)
```

---

## Session & Database Flow:

```
┌────────────────────────────────────────────────────────┐
│                   LOGIN PROCESS                        │
├────────────────────────────────────────────────────────┤
│                                                        │
│  1. User credentials दिए जाते हैं                      │
│     ↓                                                  │
│  2. Database में check होता है                         │
│     ↓                                                  │
│  3. अगर match करे:                                    │
│     └─ session['user_id'] = ...                       │
│     └─ session['user_role'] = 'patient'  ← KEY!      │
│     ↓                                                  │
│  4. Dashboard page load होता है                        │
│     └─ जो role के अनुसार base template select करता है  │
│     ↓                                                  │
│  5. सही navbar + options दिखते हैं                    │
│                                                        │
└────────────────────────────────────────────────────────┘
```

---

## Navigation Difference:

```
ALL PAGES (सभी pages):
┌─────────────────────────────┐
│ LOGOUT | LANGUAGE | ACCOUNT │
└─────────────────────────────┘

PATIENT PAGE (Green):
┌─────────────────────────────────────┐
│ DASHBOARD | SEARCH DISEASE | ACCOUNT │
└─────────────────────────────────────┘

HOSPITAL PAGE (Blue):
┌──────────────────────────────┐
│ DASHBOARD | REQUESTS | ACCOUNT│
└──────────────────────────────┘

ADMIN PAGE (Purple):
┌─────────────────────────────────────────────┐
│ DASHBOARD | HOSPITAL | DISEASE | MANAGEMENT │
└─────────────────────────────────────────────┘
```

---

## Color Scheme:

```
┌──────────────────────────────────────────┐
│  PATIENT (Green)  🟢                     │
├──────────────────────────────────────────┤
│  Navbar Background:     #c8e6c9          │
│  Navbar Text:           #1b5e20          │
│  Buttons:               #2e7d32          │
│  Highlights:            #00695c          │
└──────────────────────────────────────────┘

┌──────────────────────────────────────────┐
│  HOSPITAL (Blue)  🔵                     │
├──────────────────────────────────────────┤
│  Navbar Background:     #b3e5fc          │
│  Navbar Text:           #0277bd          │
│  Buttons:               #01579b          │
│  Highlights:            #004d7a          │
└──────────────────────────────────────────┘

┌──────────────────────────────────────────┐
│  ADMIN (Purple)  🟣                      │
├──────────────────────────────────────────┤
│  Navbar Background:     #e1bee7          │
│  Navbar Text:           #6a1b9a          │
│  Buttons:               #4a148c          │
│  Highlights:            #38006b          │
└──────────────────────────────────────────┘
```

---

## Access Control Matrix:

```
                  │ Patient | Hospital | Admin
──────────────────┼─────────┼──────────┼──────
/patient/panel    │   ✅    │    ❌    │  ❌
/hospital/dash    │   ❌    │    ✅    │  ❌
/admin/dash       │   ❌    │    ❌    │  ✅
/api/*            │  🟡    │   🟡    │  🟡
──────────────────┴─────────┴──────────┴──────

✅ = Access Allowed
❌ = Access Denied
🟡 = Role-Specific Access
```

---

## File Structure After Implementation:

```
app.py
├── @role_required() decorator
├── Login functions (role stored)
├── Logout functions (role cleared)
└── Protected routes

templates/
├── patient_base.html         ← GREEN NAVBAR
├── hospital_base.html        ← BLUE NAVBAR
├── admin_base.html           ← PURPLE NAVBAR
│
├── patient/
│   ├── index.html (with role selector)
│   ├── panel.html (extends patient_base)
│   ├── panel_login.html (with green alert)
│   └── ... (20+ more pages)
│
├── hospital/
│   ├── dashboard.html (extends hospital_base)
│   ├── login.html (with blue alert)
│   └── ... (5 more pages)
│
└── admin/
    ├── dashboard.html (extends admin_base)
    ├── login.html (with purple alert)
    └── ... (10 more pages)
```

---

## Session Data When Logged In:

```
┌─── PATIENT LOGGED IN ──────────────────┐
│ session['user_role'] = 'patient'       │
│ session['patient_id'] = 1              │
│ session['patient_name'] = 'Name'       │
│ session['patient_logged_in'] = True    │
└────────────────────────────────────────┘

┌─── HOSPITAL LOGGED IN ─────────────────┐
│ session['user_role'] = 'hospital'      │
│ session['hospital_id'] = 1             │
│ session['hospital_name'] = 'Hospital'  │
└────────────────────────────────────────┘

┌─── ADMIN LOGGED IN ────────────────────┐
│ session['user_role'] = 'admin'         │
│ session['admin_id'] = 1                │
│ session['admin_username'] = 'admin'    │
└────────────────────────────────────────┘

┌─── LOGGED OUT ─────────────────────────┐
│ session.clear() → सब empty            │
│ No user_role                          │
└────────────────────────────────────────┘
```

---

## Request Flow Example:

```
REQUEST: User Patient Panel Access करना चाहता है

Step 1: Request आता है
        GET /patient/panel

Step 2: @patient_login_required decorator check करता है
        क्या session में patient_logged_in है?
        ✅ YES → Continue
        ❌ NO → Redirect to /patient/login

Step 3: @role_required('patient') decorator check करता है
        क्या session['user_role'] == 'patient'?
        ✅ YES → Continue
        ❌ NO → Access Denied + Redirect

Step 4: Function execute होता है
        patient = Patient.query.get(patient_id)

Step 5: Template render होता है
        render_template('patient/panel.html', patient=patient)

Step 6: patient_panel.html loads करता है
        {% extends "patient_base.html" %}

Step 7: patient_base.html loads होता है
        Green navbar + Patient options

Step 8: Content block fill होता है
        patient.name और अन्य details

Step 9: Complete page browser को भेजा जाता है
        With Green navbar and Patient options only
```

---

## Unauthorized Access Example:

```
REQUEST: Hospital का Admin Dashboard access करना चाहता है

Step 1: Request आता है
        GET /admin/dashboard

        BUT session में है:
        session['user_role'] = 'hospital'
        session['hospital_id'] = 1

Step 2: @login_required_admin check करता है
        क्या 'admin_id' session में है?
        ❌ NO → Redirect to /admin/login

        OR अगर कोई hack करके admin_id भी add कर दे:

Step 3: @role_required('admin') check करता है
        क्या session['user_role'] == 'admin'?
        ❌ NO (यह 'hospital' है)

        → Flash: "Access denied. You do not have permission"
        → Redirect: /hospital/dashboard (Hospital के dashboard पर)
```

---

## User Experience Timeline:

```
TIME    PATIENT              HOSPITAL            ADMIN
────────────────────────────────────────────────────────
T0      Home Page (unauth)   Home Page (unauth)  Home Page (unauth)
        See 3 buttons        See 3 buttons       See 3 buttons

T1      Click "Patient"      Click "Hospital"    Click "Admin"

T2      /patient/login       /hospital/login     /admin/login
        (Green alert)        (Blue alert)        (Purple alert)

T3      Enter Aadhaar        Enter Email         Enter Username

T4      /patient/panel       /hospital/dash      /admin/dash
        (Green navbar)       (Blue navbar)       (Purple navbar)
        (Patient options)    (Hospital options)  (Admin options)

T5      Use features         Use features        Use features

T6      Click Logout         Click Logout        Click Logout

T7      Home Page again      Home Page again     Home Page again
```

---

## Summary:

```
┌────────────────────────────────────────────────────────┐
│                                                        │
│  3 COMPLETELY DIFFERENT EXPERIENCES                   │
│                                                        │
│  🟢 PATIENT → Green Page → Patient Options             │
│  🔵 HOSPITAL → Blue Page → Hospital Options           │
│  🟣 ADMIN → Purple Page → Admin Options               │
│                                                        │
│  हर role को सिर्फ उसके page और options दिखते हैं     │
│  दूसरे roles के pages accessible नहीं होते           │
│                                                        │
└────────────────────────────────────────────────────────┘
```
