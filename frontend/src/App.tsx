import { Routes, Route, useLocation } from 'react-router-dom'
import { Navbar } from './components/Navbar'
import { Footer } from './components/Footer'
import { CartProvider } from './features/cart/CartContext'
import { ToastProvider } from './features/toast/ToastContext'
import { Home } from './pages/Home'
import { Shop } from './pages/Shop'
import { ProductDetail } from './pages/ProductDetail'
import { Cart } from './pages/Cart'
import { Checkout } from './pages/Checkout'
import { OrderConfirmation } from './pages/OrderConfirmation'
import { OrderHistory } from './pages/OrderHistory'

export default function App() {
  const location = useLocation()
  const isHome = location.pathname === '/'

  return (
    <CartProvider>
      <ToastProvider>
        <div className="flex min-h-screen flex-col">
          <Navbar />
          {/* On non-home pages, add top padding to offset the fixed navbar */}
          <main className={`flex-1 ${isHome ? '' : 'pt-[76px]'}`}>
            <Routes>
              <Route path="/" element={<Home />} />
              <Route path="/shop" element={<Shop />} />
              <Route path="/product/:slug" element={<ProductDetail />} />
              <Route path="/cart" element={<Cart />} />
              <Route path="/checkout" element={<Checkout />} />
              <Route path="/order/:orderNumber" element={<OrderConfirmation />} />
              <Route path="/orders" element={<OrderHistory />} />
            </Routes>
          </main>
          <Footer />
        </div>
      </ToastProvider>
    </CartProvider>
  )
}
