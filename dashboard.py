"""LuckyApply Dashboard"""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st

DB_PATH = Path.home() / ".applypilot" / "applypilot.db"
PROOF_DIR = Path.home() / ".applypilot" / "proof_reports"
MASTER_RESUME = Path.home() / ".applypilot" / "resume.txt"
MASTER_PDF = Path.home() / ".applypilot" / "resume.pdf"

st.set_page_config(page_title="LuckyApply", page_icon="🍀", layout="wide")

ROLES = {
    "Content Manager": ["content manager", "content strategist", "content lead", "content director", "editorial", "content marketing"],
    "Product Manager": ["product manager", "product owner", "product lead", "product director", "program manager"],
    "Web Manager": ["web manager", "web developer", "frontend", "front end", "webmaster", "web engineer", "digital manager", "web lead", "aem", "cms"],
}

PROSPECT_PHASES = ['prospect', 'tailoring', 'tailored', 'applying', 'applied', 'callback', 'interview', 'offer', 'rejected', 'withdrawn']
PHASE_EMOJI = {
    'prospect': '🔵', 'tailoring': '🟡', 'tailored': '🟢', 'applying': '🟠',
    'applied': '🔷', 'callback': '💬', 'interview': '🎯', 'offer': '🏆',
    'rejected': '❌', 'withdrawn': '⬜',
}


def get_db():
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def q(sql, params=()):
    return pd.read_sql_query(sql, get_db(), params=params)


def q1(sql, params=()):
    return get_db().execute(sql, params).fetchone()[0]


def q1_safe(sql, params=(), default=0):
    try:
        return get_db().execute(sql, params).fetchone()[0]
    except sqlite3.OperationalError:
        return default


def role_where(role_name):
    """Return (where_clause, params) for a role's keywords."""
    kws = ROLES[role_name]
    clauses = " OR ".join(["LOWER(title) LIKE ?" for _ in kws])
    params = [f"%{kw}%" for kw in kws]
    return f"({clauses})", params


def role_count(role_name):
    """Count scored jobs matching a role."""
    wc, params = role_where(role_name)
    return q1(f"SELECT COUNT(*) FROM jobs WHERE fit_score IS NOT NULL AND {wc}", params)


# ─── Counts for tab labels ───
counts = {r: role_count(r) for r in ROLES}
prospect_count = q1_safe("SELECT COUNT(*) FROM jobs WHERE prospect_status IS NOT NULL")
resume_count = q1("SELECT COUNT(*) FROM jobs WHERE tailored_resume_path IS NOT NULL")

# ─── Header + Tabs ───
st.markdown("# 🍀 LuckyApply")

tab_labels = [f"{r} ({counts[r]})" for r in ROLES] + [f"Prospects ({prospect_count})", f"Resumes ({resume_count})"]
tabs = st.tabs(tab_labels)
role_tabs = {r: tabs[i] for i, r in enumerate(ROLES)}
tab_prospects = tabs[len(ROLES)]
tab_resumes = tabs[len(ROLES) + 1]


# ═══════════════════════════════════════════════════════════════
# ROLE TABS — one per role
# ═══════════════════════════════════════════════════════════════
def render_role_tab(role_name, tab):
    with tab:
        wc, wparams = role_where(role_name)

        # Filters
        fc1, fc2 = st.columns(2)
        search = fc1.text_input("Search", key=f"{role_name}_search")
        hide_sel = fc2.checkbox("Hide selected", key=f"{role_name}_hide")

        where = [wc, "fit_score >= 6"]
        params = list(wparams)
        if search:
            where.append("(title LIKE ? OR company LIKE ?)")
            params += [f"%{search}%"] * 2
        if hide_sel:
            where.append("prospect_status IS NULL")

        df = q(f"""
            SELECT url, title, company, site, fit_score as score, location,
                   score_reasoning, application_url,
                   CASE WHEN prospect_status IS NOT NULL THEN prospect_status ELSE '' END as status,
                   substr(discovered_at, 1, 10) as discovered
            FROM jobs
            WHERE fit_score IS NOT NULL AND {' AND '.join(where)}
            ORDER BY fit_score DESC, discovered_at DESC
            LIMIT 300
        """, params)

        if df.empty:
            st.info(f"No {role_name} jobs match your filters.")
            return

        st.caption(f"{len(df)} jobs")

        # Select all
        select_all = st.checkbox("Select all", key=f"{role_name}_selall")

        selected_urls = []
        for idx, row in df.iterrows():
            score = row["score"]
            status = row["status"]
            title = row["title"] or "Untitled"
            company = row["company"] or row["site"] or "Unknown"

            tier = "🥇" if score >= 10 else "🥈" if score >= 9 else "🥉" if score >= 8 else ""
            if score >= 8:
                label = f"{tier} **[{score}]** {title} @ {company}"
            elif score >= 7:
                label = f"[{score}] {title} @ {company}"
            else:
                label = f"[{score}] {title} @ {company}"
            if status:
                label += f" — _{status}_"

            already = bool(status)
            cc, cl = st.columns([0.04, 0.96])
            with cc:
                if not already:
                    if st.checkbox("", key=f"s_{role_name}_{idx}", value=select_all, label_visibility="collapsed"):
                        selected_urls.append(row["url"])
                else:
                    st.markdown("<span style='color:gray'>✓</span>", unsafe_allow_html=True)
            with cl:
                with st.expander(label, expanded=False):
                    e1, e2 = st.columns(2)
                    with e1:
                        st.markdown(f"**Score:** {score} | **Location:** {row['location'] or 'N/A'}")
                        if row["application_url"]:
                            st.markdown(f"[Apply Link]({row['application_url']})")
                    with e2:
                        if row["score_reasoning"]:
                            st.caption(row["score_reasoning"])
                    jd = get_db().execute("SELECT full_description FROM jobs WHERE url = ?", (row["url"],)).fetchone()
                    if jd and jd[0]:
                        st.text_area("JD", jd[0][:3000], height=200, disabled=True, key=f"jd_{role_name}_{idx}")

        if selected_urls:
            st.divider()
            if st.button(f"Add {len(selected_urls)} as Prospects", type="primary", key=f"add_{role_name}"):
                now = datetime.now(timezone.utc).isoformat()
                conn = get_db()
                for url in selected_urls:
                    conn.execute("UPDATE jobs SET prospect_status='prospect', prospect_at=? WHERE url=?", (now, url))
                conn.commit()
                st.success(f"Added {len(selected_urls)} prospects!")
                st.rerun()


for role_name in ROLES:
    render_role_tab(role_name, role_tabs[role_name])


# ═══════════════════════════════════════════════════════════════
# PROSPECTS
# ═══════════════════════════════════════════════════════════════
with tab_prospects:

    phase_counts = {p: q1_safe("SELECT COUNT(*) FROM jobs WHERE prospect_status=?", (p,)) for p in PROSPECT_PHASES}
    total_p = sum(phase_counts.values())

    st.subheader(f"Pipeline — {total_p} prospects")
    core = [p for p in PROSPECT_PHASES if phase_counts[p] > 0 or p in ('prospect', 'tailored', 'applied', 'offer')]
    if total_p > 0:
        cols = st.columns(len(core))
        for i, p in enumerate(core):
            cols[i].metric(f"{PHASE_EMOJI.get(p,'')} {p.title()}", phase_counts[p])

    st.divider()

    pf1, pf2 = st.columns(2)
    phase_filter = pf1.multiselect("Phases", PROSPECT_PHASES,
        default=[p for p in PROSPECT_PHASES if phase_counts[p] > 0] or ['prospect'], key="pf")
    p_search = pf2.text_input("Search", key="ps")

    if not phase_filter:
        phase_filter = PROSPECT_PHASES

    ph = ','.join(['?'] * len(phase_filter))
    extra = ""
    ep = list(phase_filter)
    if p_search:
        extra = " AND (title LIKE ? OR company LIKE ?)"
        ep += [f"%{p_search}%"] * 2

    df_p = q(f"""
        SELECT url, title, company, site, fit_score as score, prospect_status as phase,
               prospect_at, application_url, tailored_resume_path, cover_letter_path,
               applied_at, response_status, response_notes, score_reasoning, location
        FROM jobs WHERE prospect_status IN ({ph}){extra}
        ORDER BY CASE prospect_status
            WHEN 'offer' THEN 1 WHEN 'interview' THEN 2 WHEN 'callback' THEN 3
            WHEN 'applied' THEN 4 WHEN 'applying' THEN 5 WHEN 'tailored' THEN 6
            WHEN 'tailoring' THEN 7 WHEN 'prospect' THEN 8 ELSE 9
        END, fit_score DESC
    """, ep)

    if df_p.empty:
        st.info("No prospects yet. Select jobs from the role tabs!")
    else:
        for idx, row in df_p.iterrows():
            phase = row["phase"]
            score = row["score"] or 0
            title = row["title"] or "Untitled"
            company = row["company"] or row["site"] or "Unknown"
            tier = "🥇" if score >= 10 else "🥈" if score >= 9 else "🥉" if score >= 8 else ""
            has_r = bool(row["tailored_resume_path"])
            has_c = bool(row["cover_letter_path"])

            hdr = f"{PHASE_EMOJI.get(phase,'⬜')} {tier} **{title}** @ {company} — [{score}] {'📄' if has_r else ''}{'✉️' if has_c else ''}"

            with st.expander(hdr, expanded=(phase in ('prospect', 'callback', 'interview', 'offer'))):
                i1, i2 = st.columns(2)
                with i1:
                    st.markdown(f"**Score:** {score} | **Location:** {row['location'] or 'N/A'} | **Phase:** {phase}")
                    if row["application_url"]:
                        st.markdown(f"[Apply Link]({row['application_url']})")
                    if row["prospect_at"]:
                        st.caption(f"Added: {str(row['prospect_at'])[:10]}")
                    if row["applied_at"]:
                        st.caption(f"Applied: {str(row['applied_at'])[:10]}")
                with i2:
                    if row["score_reasoning"]:
                        st.caption(row["score_reasoning"])
                    if row["response_notes"]:
                        st.info(row["response_notes"])

                st.markdown("---")
                p1, p2, p3 = st.columns([2, 2, 1])
                with p1:
                    new_ph = st.selectbox("Move to", PROSPECT_PHASES,
                        index=PROSPECT_PHASES.index(phase) if phase in PROSPECT_PHASES else 0, key=f"ph_{idx}")
                with p2:
                    notes = st.text_input("Notes", value=row["response_notes"] or "", key=f"nt_{idx}")
                with p3:
                    if st.button("Update", key=f"up_{idx}"):
                        now = datetime.now(timezone.utc).isoformat()
                        conn = get_db()
                        conn.execute("UPDATE jobs SET prospect_status=?, response_notes=?, prospect_at=? WHERE url=?",
                                     (new_ph, notes or None, now, row["url"]))
                        if new_ph in ('callback', 'interview', 'offer', 'rejected'):
                            conn.execute("UPDATE jobs SET response_status=?, response_at=? WHERE url=?",
                                         (new_ph, now, row["url"]))
                        conn.commit()
                        st.rerun()

                if has_r:
                    rp = Path(row["tailored_resume_path"])
                    if rp.exists():
                        with st.expander("📄 Resume"):
                            c = rp.read_text(encoding="utf-8")
                            try:
                                d = json.loads(c)
                                pi = d.get("personalInfo", {})
                                st.markdown(f"**{pi.get('name','')}** — {pi.get('title','')}")
                                st.markdown(d.get("summary", ""))
                                for exp in d.get("workExperience", [])[:4]:
                                    st.markdown(f"**{exp.get('title','')}** @ {exp.get('company','')} ({exp.get('years','')})")
                                    for b in exp.get("description", [])[:3]:
                                        st.markdown(f"- {b}")
                            except (json.JSONDecodeError, TypeError):
                                st.text(c[:3000])
                if has_c:
                    cp = Path(row["cover_letter_path"])
                    if cp.exists():
                        with st.expander("✉️ Cover Letter"):
                            st.text(cp.read_text(encoding="utf-8")[:2000])


# ═══════════════════════════════════════════════════════════════
# RESUMES
# ═══════════════════════════════════════════════════════════════
with tab_resumes:

    st.subheader("Master Resume")
    m1, m2 = st.columns(2)
    with m1:
        if MASTER_RESUME.exists():
            mt = MASTER_RESUME.read_text(encoding="utf-8")
            st.text_area("Master (plain text)", mt[:5000], height=400, disabled=True, key="mv")
        elif MASTER_PDF.exists():
            st.info(f"PDF only: {MASTER_PDF}")
        else:
            st.warning("No master resume found")
    with m2:
        if MASTER_RESUME.exists():
            st.download_button("Download .txt", mt, file_name="master_resume.txt")
        if MASTER_PDF.exists():
            st.download_button("Download .pdf", MASTER_PDF.read_bytes(), file_name="master_resume.pdf")
        st.markdown("---")
        if MASTER_RESUME.exists():
            ed = st.text_area("Edit master", mt, height=400, key="me")
            if st.button("Save"):
                MASTER_RESUME.write_text(ed, encoding="utf-8")
                st.success("Saved!")
                st.rerun()

    st.divider()
    st.subheader("Tailored Variations")

    df_v = q("""
        SELECT title, company, site, fit_score as score, tailored_resume_path, cover_letter_path,
               tailored_at, prospect_status, url
        FROM jobs WHERE tailored_resume_path IS NOT NULL ORDER BY tailored_at DESC LIMIT 100
    """)

    if df_v.empty:
        st.info("No tailored resumes yet. Run `applypilot bridge`.")
    else:
        for idx, row in df_v.iterrows():
            title = row["title"] or "Untitled"
            company = row["company"] or row["site"] or "Unknown"
            score = row["score"] or 0
            tier = "🥇" if score >= 10 else "🥈" if score >= 9 else "🥉" if score >= 8 else ""
            phase = row["prospect_status"] or ""

            rp = Path(row["tailored_resume_path"]) if row["tailored_resume_path"] else None
            cp = Path(row["cover_letter_path"]) if row["cover_letter_path"] else None

            with st.expander(f"{tier} [{score}] {title} @ {company}" + (f" — _{phase}_" if phase else "")):
                v1, v2 = st.columns(2)
                with v1:
                    if rp and rp.exists():
                        content = rp.read_text(encoding="utf-8")
                        try:
                            d = json.loads(content)
                            pi = d.get("personalInfo", {})
                            lines = [f"**{pi.get('name','')}** — {pi.get('title','')}", "", d.get("summary", "")]
                            for exp in d.get("workExperience", []):
                                lines.append(f"\n**{exp.get('title','')}** @ {exp.get('company','')} ({exp.get('years','')})")
                                lines += [f"- {b}" for b in exp.get("description", [])]
                            add = d.get("additional", {})
                            if add.get("technicalSkills"):
                                lines.append(f"\n**Skills:** {', '.join(add['technicalSkills'])}")
                            st.markdown("\n".join(lines))
                        except (json.JSONDecodeError, TypeError):
                            st.text(content[:3000])
                        with st.expander("Edit"):
                            ev = st.text_area("", content, height=300, key=f"ve_{idx}")
                            if st.button("Save", key=f"vs_{idx}"):
                                rp.write_text(ev, encoding="utf-8")
                                st.success("Saved!")
                        st.download_button("Download", content, file_name=rp.name, key=f"vd_{idx}")
                with v2:
                    if cp and cp.exists():
                        cl = cp.read_text(encoding="utf-8")
                        st.text(cl[:2000])
                        st.download_button("Download CL", cl, file_name=cp.name, key=f"vc_{idx}")
                    else:
                        st.caption("No cover letter")
                    if row["tailored_at"]:
                        st.caption(f"Tailored: {str(row['tailored_at'])[:10]}")
