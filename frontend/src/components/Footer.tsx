import { Link } from 'react-router-dom'

/* ────────────────────────────────────────────────────────────────────────────
 * Footer — Polished luxury footer matching the refined brand aesthetic
 * ──────────────────────────────────────────────────────────────────────── */

export function Footer() {
  return (
    <footer className="bg-stone-900 text-stone-300">
      <div className="mx-auto max-w-7xl px-6 lg:px-10">
        {/* Main footer content */}
        <div className="grid grid-cols-1 gap-10 py-16 sm:grid-cols-2 lg:grid-cols-4">
          {/* Brand */}
          <div className="sm:col-span-2 lg:col-span-1">
            <h3 className="font-serif text-2xl font-semibold tracking-[0.08em] uppercase text-white">
              FineFit
            </h3>
            <p className="mt-4 text-sm leading-relaxed text-stone-400">
              Modern fashion for the refined wardrobe. Curated collections
              designed with precision and care.
            </p>
          </div>

          {/* Shop */}
          <div>
            <h4 className="text-xs font-medium uppercase tracking-widest text-white mb-4">
              Shop
            </h4>
            <ul className="space-y-3 text-sm">
              <li>
                <Link to="/shop" className="text-stone-400 hover:text-white transition-colors">
                  All Products
                </Link>
              </li>
              <li>
                <Link to="/shop?category=women" className="text-stone-400 hover:text-white transition-colors">
                  Women
                </Link>
              </li>
              <li>
                <Link to="/shop?category=men" className="text-stone-400 hover:text-white transition-colors">
                  Men
                </Link>
              </li>
              <li>
                <Link to="/shop" className="text-stone-400 hover:text-white transition-colors">
                  New Arrivals
                </Link>
              </li>
            </ul>
          </div>

          {/* Company */}
          <div>
            <h4 className="text-xs font-medium uppercase tracking-widest text-white mb-4">
              Company
            </h4>
            <ul className="space-y-3 text-sm">
              <li>
                <span className="text-stone-400">About Us</span>
              </li>
              <li>
                <span className="text-stone-400">Careers</span>
              </li>
              <li>
                <span className="text-stone-400">Sustainability</span>
              </li>
            </ul>
          </div>

          {/* Contact */}
          <div>
            <h4 className="text-xs font-medium uppercase tracking-widest text-white mb-4">
              Contact
            </h4>
            <ul className="space-y-3 text-sm">
              <li className="text-stone-400">support@finefit.com</li>
              <li className="text-stone-400">+880 1234 567890</li>
            </ul>
          </div>
        </div>

        {/* Bottom bar */}
        <div className="border-t border-stone-700/50 py-6 flex flex-col sm:flex-row items-center justify-between gap-4">
          <p className="text-xs text-stone-500">
            © {new Date().getFullYear()} FineFit. All rights reserved.
          </p>
          <div className="flex gap-6 text-xs text-stone-500">
            <span>Privacy Policy</span>
            <span>Terms of Service</span>
          </div>
        </div>
      </div>
    </footer>
  )
}
