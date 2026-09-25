import { Shield, ChevronRight } from 'lucide-react'
import { Link } from 'react-router-dom'

const SECTIONS = [
  {
    id: 'information-we-collect',
    title: '1. Information We Collect',
    content: `We collect information you provide directly to us, such as when you create an account, place an order, contact support, or interact with our AI voice agent (Aura). This includes:

• **Account Data:** Name, email address, phone number, and password.
• **Order & Transaction Data:** Purchase history, delivery addresses, payment method details (processed securely through our payment partners — we do not store raw card numbers).
• **Voice & Chat Interactions:** Audio recordings and transcripts of voice calls and chat sessions with Aura, used solely to fulfil your request and improve service quality.
• **Device & Usage Data:** Browser type, IP address, pages visited, and interaction timestamps, collected via cookies and similar technologies.`,
  },
  {
    id: 'how-we-use',
    title: '2. How We Use Your Information',
    content: `We use the information we collect to:

• Provide, operate, and maintain the RetailVoice platform and NovaMart storefront.
• Process and fulfil your orders and returns.
• Power the Aura AI Voice & Support Agent to resolve your enquiries in real time.
• Send transactional communications (order confirmations, OTP security codes, delivery updates).
• Detect fraud, enforce our Terms of Service, and comply with legal obligations.
• Analyse aggregated, anonymised usage patterns to improve platform performance.

We do **not** sell your personal data to third parties.`,
  },
  {
    id: 'cookies',
    title: '3. Cookies & Tracking',
    content: `We use strictly necessary cookies to keep you signed in and maintain your session. With your consent, we also use:

• **Analytics Cookies:** To understand how users navigate the platform (e.g. page popularity, drop-off points).
• **Preference Cookies:** To remember your language and display settings.

You can withdraw your consent at any time via the cookie banner or your browser settings. Withdrawing consent will not affect the lawfulness of processing based on consent given before withdrawal.`,
  },
  {
    id: 'data-sharing',
    title: '4. Data Sharing & Third Parties',
    content: `We share your information only where necessary:

• **Payment Processors:** We pass payment details to our PCI-DSS-compliant payment partners to complete transactions.
• **Delivery Partners:** Order and address data are shared with logistics providers to fulfil deliveries.
• **Cloud Infrastructure:** Our platform runs on ISO 27001-certified cloud providers. Data is processed within the EU/EEA or under Standard Contractual Clauses.
• **Legal Requests:** We may disclose information if required by law, court order, or to protect the rights and safety of our users.`,
  },
  {
    id: 'retention',
    title: '5. Data Retention',
    content: `We retain your personal data for as long as your account is active or as needed to provide services. You may request account deletion at any time via our support channel. Upon deletion, we anonymise or erase your data within 30 days, except where we are required to retain records for legal or regulatory purposes (e.g., financial records for 7 years).`,
  },
  {
    id: 'your-rights',
    title: '6. Your Rights',
    content: `Depending on your jurisdiction, you may have the right to:

• **Access** the personal data we hold about you.
• **Rectify** inaccurate or incomplete information.
• **Erase** your data ("right to be forgotten").
• **Restrict** or **object to** certain processing activities.
• **Data Portability:** Receive your data in a machine-readable format.
• **Withdraw Consent** for non-essential processing at any time.

To exercise any of these rights, please contact us at **privacy@retailvoice.ai**.`,
  },
  {
    id: 'security',
    title: '7. Security',
    content: `We implement industry-standard security measures including TLS 1.3 encryption in transit, AES-256 encryption at rest, multi-factor authentication, and mandatory OTP verification for sensitive actions such as placing orders. We conduct regular security audits and penetration tests. Despite these measures, no system is completely secure; please safeguard your credentials and report suspected unauthorised access immediately.`,
  },
  {
    id: 'children',
    title: '8. Children\'s Privacy',
    content: `RetailVoice is not directed at individuals under the age of 16. We do not knowingly collect personal data from children. If you believe we have inadvertently collected such data, please contact us immediately and we will delete it promptly.`,
  },
  {
    id: 'changes',
    title: '9. Changes to This Policy',
    content: `We may update this Privacy Policy periodically. When we make material changes, we will notify you via email or a prominent in-app notice at least 14 days before the changes take effect. Continued use of the platform after the effective date constitutes acceptance of the updated policy.`,
  },
  {
    id: 'contact',
    title: '10. Contact Us',
    content: `If you have questions, concerns, or requests regarding this Privacy Policy or our data practices, please reach out:

• **Email:** privacy@retailvoice.ai
• **Data Protection Officer:** dpo@retailvoice.ai
• **Postal Address:** RetailVoice AI Ltd., 12 Innovation Quarter, Tech Park, London, EC2A 4NE, United Kingdom`,
  },
]

export function PrivacyPolicy() {
  return (
    <div className="min-h-full bg-ink-50">
      {/* Hero */}
      <div className="bg-gradient-to-br from-brand-900 via-brand-800 to-violet-900 px-6 py-14 text-center">
        <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-white/10 ring-1 ring-white/20 mb-4">
          <Shield className="h-7 w-7 text-white" />
        </div>
        <h1 className="text-3xl font-extrabold tracking-tight text-white">Privacy Policy</h1>
        <p className="mt-2 text-brand-200 text-sm">
          Last updated: <span className="font-semibold text-white">1 September 2026</span>
        </p>
        <p className="mt-4 max-w-xl mx-auto text-sm text-brand-100/80 leading-relaxed">
          RetailVoice AI Ltd. ("we", "us", "our") is committed to protecting your personal data. This policy explains
          what we collect, why, and how you can control it.
        </p>
      </div>

      {/* Breadcrumb */}
      <nav className="mx-auto max-w-4xl px-6 py-3 flex items-center gap-1 text-xs text-ink-400">
        <Link to="/" className="hover:text-brand-600 transition">Home</Link>
        <ChevronRight className="h-3 w-3" />
        <span className="text-ink-600 font-medium">Privacy Policy</span>
      </nav>

      {/* Table of Contents */}
      <div className="mx-auto max-w-4xl px-6 pb-4">
        <div className="rounded-xl border border-ink-200 bg-white p-5 shadow-xs">
          <p className="text-xs font-semibold uppercase tracking-wider text-ink-400 mb-3">Contents</p>
          <ol className="space-y-1">
            {SECTIONS.map((s) => (
              <li key={s.id}>
                <a
                  href={`#${s.id}`}
                  className="text-sm text-brand-600 hover:text-brand-700 hover:underline transition"
                >
                  {s.title}
                </a>
              </li>
            ))}
          </ol>
        </div>
      </div>

      {/* Content */}
      <div className="mx-auto max-w-4xl px-6 pb-16 space-y-6">
        {SECTIONS.map((s) => (
          <section
            key={s.id}
            id={s.id}
            className="rounded-xl border border-ink-200 bg-white px-7 py-6 shadow-xs scroll-mt-24"
          >
            <h2 className="text-base font-bold text-ink-900 mb-3">{s.title}</h2>
            <div className="prose prose-sm prose-ink max-w-none text-ink-600 leading-relaxed whitespace-pre-line">
              {s.content.split('\n').map((line, i) => {
                if (line.startsWith('• **') || line.startsWith('• ')) {
                  const parts = line.replace('• ', '').split(/\*\*(.*?)\*\*/)
                  return (
                    <p key={i} className="flex gap-2 mt-1.5">
                      <span className="text-brand-500 mt-0.5 shrink-0">•</span>
                      <span>
                        {parts.map((p, j) =>
                          j % 2 === 1 ? <strong key={j} className="text-ink-800">{p}</strong> : p
                        )}
                      </span>
                    </p>
                  )
                }
                if (line.trim() === '') return <div key={i} className="h-2" />
                const parts = line.split(/\*\*(.*?)\*\*/)
                return (
                  <p key={i} className="mt-1">
                    {parts.map((p, j) =>
                      j % 2 === 1 ? <strong key={j} className="text-ink-800">{p}</strong> : p
                    )}
                  </p>
                )
              })}
            </div>
          </section>
        ))}

        <p className="text-center text-xs text-ink-400 pt-4">
          © 2026 RetailVoice AI Ltd. · All rights reserved ·{' '}
          <Link to="/terms" className="hover:text-brand-600 transition">Terms of Service</Link>
        </p>
      </div>
    </div>
  )
}
