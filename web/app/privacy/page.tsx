// The privacy notice of the hosted demo (to-do item 27): public, no login. It states in plain words what the app is,
// what a person enters and where it goes, the safeguards, what never leaves, how long things are kept and whom to
// ask. The facts are those of README section 9 and docs/compliance/; change them there and here together.

import Link from "next/link";

export const metadata = { title: "Privacy notice · Compliance Assistant" };

const RETENTION_DAYS = 30;
const REPO = "https://github.com/aishwaryamuralikrishnan/Compliance_Assessment_Agent";

export default function PrivacyPage() {
  return (
    <main className="evalshell">
      <header className="evalbar">
        <Link href="/login" className="row" style={{ gap: 10, color: "inherit", textDecoration: "none" }}>
          <span className="logo-sm" aria-hidden="true">C</span><b>Compliance Assistant</b><span className="sep">/</span><span className="muted">Privacy notice</span>
        </Link>
        <span className="grow" />
        <Link className="btn sm" href="/evaluation">Evaluation report</Link>
      </header>
      <div className="evalbody notice">
        <div>
          <h2 style={{ fontSize: 22, fontWeight: 700, margin: 0 }}>Privacy notice for the hosted demo</h2>
          <p className="muted" style={{ margin: "4px 0 0 0" }}>Last updated 3 November 2026 · a Turing College capstone project by Aishwarya Muralikrishnan</p>
        </div>

        <section className="card pad">
          <h3>What this is</h3>
          <p>An AI system. The Compliance Assistant reads a feature description or a question and drafts a first assessment against the GDPR and the EU AI Act, with article citations checked against the law&apos;s text. The draft is written by AI models; a human reviewer in the role of Data Protection Officer decides what goes on record. It is a demonstration for a course project, not legal advice and not a service for real compliance work.</p>
          <p><b>Please do not enter real personal data.</b> Describe features with made-up names and figures. The demo is not meant to process information about real people, and the examples it was built for contain none.</p>
        </section>

        <section className="card pad">
          <h3>What you enter, and where it goes</h3>
          <p>The text you type is first screened in the app: personal data the screen recognises (names, e-mail addresses, phone numbers, identifiers) is redacted before any AI model sees it. The redacted text, the passages of law retrieved for it and a few seeded facts about a fictional organisation are then sent to AI models through <b>OpenRouter</b>, a model gateway in the United States, which forwards them to the model providers the app is configured for: <b>OpenAI</b> (the assessment and the quick answers, and the embedding of your text for the search), <b>Google</b> (a small model that classifies the input and ranks the retrieved passages). The evaluation report was produced with a model by <b>Anthropic</b> as the judge; that model is not used when you use the app.</p>
          <p>These providers are sub-processors of the demo. The gateway&apos;s account is set so that every provider must serve the request under <b>zero data retention</b> (Google&apos;s models under its &quot;safety retention&quot;, a short retention to detect abuse, never for training), every option that would allow training on requests is switched off, and the app sends the same policy with each request itself. OpenRouter&apos;s data-processing agreement is available to enterprise customers only; this demo runs under OpenRouter&apos;s terms and privacy policy and the settings above. Transfers to the United States rest on the standard contractual clauses the gateway and the providers state in those documents.</p>
        </section>

        <section className="card pad">
          <h3>What stays in the app</h3>
          <p>The app&apos;s own database is hosted in the European Union (Frankfurt). It holds the conversations and their saved state, the assessments and the reviewer&apos;s decisions, the processing register, the long-term memory the reviewer approves, and the user accounts. None of this is sent to the model providers, except the seeded organisation facts and approved memory items that the agent reads while drafting.</p>
          <p>If you sign in with Google, the app stores your e-mail address, your name as Google gives it and Google&apos;s account identifier, to recognise you at the next sign-in and to record who requested or approved what. Nothing else from your Google account is requested. The session is a signed cookie that lasts eight hours.</p>
        </section>

        <section className="card pad">
          <h3>How long</h3>
          <p>Finished conversations and their saved state are deleted after <b>{RETENTION_DAYS} days</b> by a scheduled job. Assessments, decisions and register entries are records of the demo and are kept until the demo is reset, which happens before showcases. User accounts are kept while the demo runs. The hosted demo may be reset or taken down at any time.</p>
        </section>

        <section className="card pad">
          <h3>Your rights and whom to ask</h3>
          <p>Under the GDPR you can ask what the demo holds about you, have it corrected or deleted, or object to its use. For this demo the responsible person is the author, Aishwarya Muralikrishnan; the quickest way to reach her is to open an issue in the project&apos;s repository, <a href={REPO + "/issues"} target="_blank" rel="noreferrer">github.com/aishwaryamuralikrishnan/Compliance_Assessment_Agent</a>, with the e-mail address you signed in with (do not post anything else personal in the issue). A deletion request is carried out within a few days with the project&apos;s own command (<code>admin.py forget</code>): your account, your conversations with their saved state, the assessments and review requests you made and your own memory items are deleted; a register entry or an approved memory item that the organisation keeps as its record stays, with your name replaced by &quot;deleted user&quot;. You may also complain to a data protection authority.</p>
        </section>

        <p className="small muted">The source code, the configuration that sets the data policy (<code>config/models.yaml</code>) and the gateway&apos;s documents and settings as saved on 3 November 2026 (<code>docs/compliance/</code>) are in the <a href={REPO} target="_blank" rel="noreferrer">public repository</a>, so every statement above can be checked against the code that runs.</p>
      </div>
    </main>
  );
}
