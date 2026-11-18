export default function PrivacyPolicy() {
  return (
    <div className="min-h-screen bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-3xl mx-auto bg-white p-8 border border-gray-200 shadow-sm">
        <h1 className="text-3xl font-bold text-gray-900 mb-6">Privacy Policy</h1>
        <p className="text-sm text-gray-500 mb-6">Last updated: November 18, 2026</p>

        <div className="space-y-4 text-gray-700 text-sm leading-relaxed">
          <p>
            Welcome to <strong>Complete Trade Auto</strong> ("we", "our", or "us"). We respect your privacy and are committed to protecting your personal data. This privacy policy informs you how we handle your information when you use our automated Bitcoin trading platform and Instagram/WhatsApp notification services.
          </p>

          <h2 className="text-lg font-semibold text-gray-900 mt-4">1. Information We Collect</h2>
          <p>
            When you connect your Meta / Instagram account or use our trading dashboard, we may collect basic profile information such as your user ID, username, and messages sent through the Instagram Messaging API strictly for the purpose of sending automated trade execution alerts, market regime analysis, and PnL summaries to you.
          </p>

          <h2 className="text-lg font-semibold text-gray-900 mt-4">2. How We Use Your Information</h2>
          <p>
            We use the collected information solely to:
          </p>
          <ul className="list-disc pl-5 space-y-1">
            <li>Deliver real-time trade signals, entry/exit notifications, and equity updates via Instagram Direct Message.</li>
            <li>Maintain and secure the automated trading engine operations.</li>
          </ul>

          <h2 className="text-lg font-semibold text-gray-900 mt-4">3. Data Security & Sharing</h2>
          <p>
            We implement robust security measures to protect your credentials and data. We do not sell, trade, or otherwise transfer your personal information to outside parties. All API keys and tokens are encrypted and stored securely.
          </p>

          <h2 className="text-lg font-semibold text-gray-900 mt-4">4. Contact Us</h2>
          <p>
            If you have any questions regarding this Privacy Policy, you can reach out via our GitHub repository or support channel.
          </p>
        </div>
      </div>
    </div>
  )
}
