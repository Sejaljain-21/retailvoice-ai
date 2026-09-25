import { FileText, ChevronRight } from 'lucide-react'
import { Link } from 'react-router-dom'

const SECTIONS = [
  {
    id: 'acceptance',
    title: '1. Acceptance of Terms',
    content: `By accessing or using the RetailVoice platform (including the NovaMart storefront, Aura AI Voice & Support Agent, and all related services), you agree to be bound by these Terms of Service ("Terms") and our Privacy Policy. If you do not agree, you must not use the platform.

These Terms constitute a legally binding agreement between you and RetailVoice AI Ltd. ("RetailVoice", "we", "us", "our"), registered in England & Wales (Company No. 14867321).`,
  },
  {
    id: 'eligibility',
    title: '2. Eligibility & Account Registration',
    content: `You must be at least 16 years of age to use RetailVoice. By registering, you confirm that:

• The information you provide is accurate, current, and complete.
• You are responsible for maintaining the confidentiality of your account credentials.
• You will notify us immediately of any unauthorised use of your account.
• You will not share your account with third parties.

We reserve the right to suspend or terminate accounts that provide false information or breach these Terms.`,
  },
  {
    id: 'aura-ai',
    title: '3. Aura AI Voice & Support Agent',
    content: `The Aura AI Voice & Support Agent is an automated system designed to assist with product enquiries, order management, and customer support. You acknowledge that:

• Aura's responses are AI-generated and may occasionally be inaccurate.
• Aura does not provide professional legal, medical, or financial advice.
• Voice sessions may be recorded and transcribed to fulfil your request and improve service quality, as described in our Privacy Policy.
• Sensitive actions (such as placing orders) require mandatory OTP verification for your security. You must not share OTP codes with anyone, including agents claiming to represent RetailVoice.`,
  },
  {
    id: 'orders',
    title: '4. Orders, Pricing & Payment',
    content: `**Placing an Order:** An order confirmation email constitutes acceptance of your offer to purchase. We reserve the right to cancel orders due to pricing errors, stock unavailability, or fraud detection.

**Pricing:** All prices displayed are inclusive of applicable taxes unless stated otherwise. Prices may change without notice, but confirmed order prices are honoured.

**Payment:** Payment is processed at the time of order via our PCI-DSS-compliant payment partners. We accept major credit/debit cards and approved digital wallets.

**Promotions:** Discount codes and promotional offers are subject to their own terms and may not be combined unless explicitly stated.`,
  },
  {
    id: 'returns',
    title: '5. Returns & Refunds',
    content: `You have the right to return most items within 30 days of delivery for a full refund, subject to the following:

• Items must be unused, in original packaging, and accompanied by proof of purchase.
• Certain categories (perishables, hygiene products, digital downloads) are non-returnable.
• Refunds are processed to the original payment method within 5–10 business days of receiving the returned item.
• Return shipping costs are the customer's responsibility unless the item is defective or incorrectly supplied.

To initiate a return, contact Aura or our support team via the platform.`,
  },
  {
    id: 'intellectual-property',
    title: '6. Intellectual Property',
    content: `All content on the RetailVoice platform — including but not limited to text, graphics, logos, UI designs, software, and AI model outputs — is the property of RetailVoice AI Ltd. or its licensors and is protected by applicable intellectual property laws.

You are granted a limited, non-exclusive, non-transferable licence to access and use the platform for personal, non-commercial purposes. You may not:

• Copy, reproduce, or distribute platform content without written permission.
• Reverse-engineer, decompile, or attempt to extract source code from our software.
• Use the platform to train competing AI models or automated systems.`,
  },
  {
    id: 'prohibited',
    title: '7. Prohibited Conduct',
    content: `You agree not to:

• Use the platform for any unlawful, fraudulent, or harmful purpose.
• Attempt to gain unauthorised access to our systems or another user's account.
• Upload or transmit malicious code, spam, or unsolicited communications.
• Abuse, harass, or threaten our support agents or AI system.
• Scrape, crawl, or systematically extract platform data without prior written consent.
• Use automated bots or scripts to interact with Aura outside of authorised integrations.

Violation of these prohibitions may result in immediate account suspension and legal action.`,
  },
  {
    id: 'disclaimers',
    title: '8. Disclaimers & Limitation of Liability',
    content: `**"As Is" Service:** The platform is provided "as is" and "as available" without warranties of any kind, express or implied, including fitness for a particular purpose or uninterrupted availability.

**AI Accuracy:** While we strive for accuracy, AI-generated content (including Aura's responses) may contain errors. Always verify critical information independently.

**Limitation:** To the fullest extent permitted by law, RetailVoice's total liability to you for any claims arising under these Terms shall not exceed the greater of (a) £100 or (b) the total amount paid by you to RetailVoice in the 12 months preceding the claim.

**Consequential Damages:** We are not liable for indirect, incidental, special, or consequential damages, including loss of profits or data.`,
  },
  {
    id: 'termination',
    title: '9. Termination',
    content: `You may terminate your account at any time by contacting our support team. We may suspend or terminate your access immediately, without notice, if we believe you have breached these Terms or posed a risk to the platform or other users.

Upon termination, your right to use the platform ceases immediately. Provisions that by their nature should survive termination (including intellectual property, disclaimers, and governing law) shall do so.`,
  },
  {
    id: 'governing-law',
    title: '10. Governing Law & Disputes',
    content: `These Terms are governed by and construed in accordance with the laws of England and Wales. Any disputes shall be subject to the exclusive jurisdiction of the courts of England and Wales, without prejudice to your rights as a consumer under applicable local law.

We encourage you to contact us first to resolve disputes amicably. For unresolved disputes, you may have the right to use an Alternative Dispute Resolution (ADR) scheme as required by applicable consumer protection regulations.`,
  },
  {
    id: 'changes',
    title: '11. Changes to These Terms',
    content: `We may revise these Terms at any time. Material changes will be communicated via email or in-app notification at least 14 days in advance. Continued use of the platform after the effective date constitutes your agreement to the revised Terms.`,
  },
  {
    id: 'contact',
    title: '12. Contact',
    content: `For questions about these Terms, please contact:

• **Email:** legal@retailvoice.ai
• **Postal Address:** RetailVoice AI Ltd., 12 Innovation Quarter, Tech Park, London, EC2A 4NE, United Kingdom`,
  },
]

export function TermsOfService() {
  return (
    <div className="min-h-full bg-ink-50">
      {/* Hero */}
      <div className="bg-gradient-to-br from-ink-900 via-ink-800 to-brand-900 px-6 py-14 text-center">
        <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-white/10 ring-1 ring-white/20 mb-4">
          <FileText className="h-7 w-7 text-white" />
        </div>
        <h1 className="text-3xl font-extrabold tracking-tight text-white">Terms of Service</h1>
        <p className="mt-2 text-ink-300 text-sm">
          Last updated: <span className="font-semibold text-white">1 September 2026</span>
        </p>
        <p className="mt-4 max-w-xl mx-auto text-sm text-ink-100/80 leading-relaxed">
          Please read these Terms carefully before using the RetailVoice platform. They govern your access to our
          services and the NovaMart AI shopping experience.
        </p>
      </div>

      {/* Breadcrumb */}
      <nav className="mx-auto max-w-4xl px-6 py-3 flex items-center gap-1 text-xs text-ink-400">
        <Link to="/" className="hover:text-brand-600 transition">Home</Link>
        <ChevronRight className="h-3 w-3" />
        <span className="text-ink-600 font-medium">Terms of Service</span>
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
          <Link to="/privacy" className="hover:text-brand-600 transition">Privacy Policy</Link>
        </p>
      </div>
    </div>
  )
}
