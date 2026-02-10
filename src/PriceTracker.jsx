import React, { useState, useEffect } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { TrendingUp, TrendingDown, Minus, Plus, Search, Calendar, DollarSign, Package, BarChart3, Bell } from 'lucide-react';

const CATEGORIES = ['Laptops', 'Monitors', 'Storage', 'Networking', 'Peripherals', 'Components', 'Servers'];

const SAMPLE_PRODUCTS = [
  { id: 1, name: 'Dell XPS 15 9530', category: 'Laptops', url: 'example.com/dell-xps', basePrice: 1899 },
  { id: 2, name: 'LG UltraGear 27GN950', category: 'Monitors', url: 'example.com/lg-monitor', basePrice: 799 },
  { id: 3, name: 'Samsung 990 PRO 2TB', category: 'Storage', url: 'example.com/samsung-ssd', basePrice: 189 },
  { id: 4, name: 'UniFi Dream Machine Pro', category: 'Networking', url: 'example.com/ubiquiti', basePrice: 379 },
  { id: 5, name: 'Logitech MX Master 3S', category: 'Peripherals', url: 'example.com/logitech', basePrice: 99 },
  { id: 6, name: 'AMD Ryzen 9 7950X', category: 'Components', url: 'example.com/amd-cpu', basePrice: 549 },
];

export default function PriceTracker() {
  const [products, setProducts] = useState([]);
  const [filteredProducts, setFilteredProducts] = useState([]);
  const [selectedCategory, setSelectedCategory] = useState('All');
  const [searchQuery, setSearchQuery] = useState('');
  const [newProduct, setNewProduct] = useState({ name: '', category: 'Laptops', url: '' });
  const [showAddForm, setShowAddForm] = useState(false);
  const [selectedProduct, setSelectedProduct] = useState(null);
  const [lastCheck, setLastCheck] = useState(new Date());
  const [priceChanges, setPriceChanges] = useState([]);

  // Initialize with sample data
  useEffect(() => {
    const initProducts = SAMPLE_PRODUCTS.map(p => ({
      ...p,
      currentPrice: p.basePrice,
      priceHistory: generateInitialHistory(p.basePrice),
      lastChecked: new Date().toISOString(),
      priceChange: 0,
      changePercent: 0
    }));
    setProducts(initProducts);
    setFilteredProducts(initProducts);
  }, []);

  // Generate realistic price history
  function generateInitialHistory(basePrice) {
    const history = [];
    const days = 30;
    for (let i = days; i >= 0; i--) {
      const date = new Date();
      date.setDate(date.getDate() - i);
      const variance = (Math.random() - 0.5) * 0.15; // ±15% variance
      const price = Math.round(basePrice * (1 + variance));
      history.push({
        date: date.toISOString().split('T')[0],
        price: price
      });
    }
    return history;
  }

  // Simulate price check
  const checkPrices = () => {
    const changes = [];
    const updatedProducts = products.map(product => {
      // Simulate price change (±10%)
      const change = (Math.random() - 0.5) * 0.2;
      const newPrice = Math.round(product.currentPrice * (1 + change));
      const priceDiff = newPrice - product.currentPrice;
      const percentChange = ((priceDiff / product.currentPrice) * 100).toFixed(2);

      if (Math.abs(priceDiff) > 5) {
        changes.push({
          productName: product.name,
          oldPrice: product.currentPrice,
          newPrice: newPrice,
          change: priceDiff,
          percent: percentChange,
          timestamp: new Date().toISOString()
        });
      }

      const newHistory = [...product.priceHistory, {
        date: new Date().toISOString().split('T')[0],
        price: newPrice
      }].slice(-30); // Keep last 30 days

      return {
        ...product,
        currentPrice: newPrice,
        priceHistory: newHistory,
        lastChecked: new Date().toISOString(),
        priceChange: priceDiff,
        changePercent: percentChange
      };
    });

    setProducts(updatedProducts);
    setFilteredProducts(filterProducts(updatedProducts, selectedCategory, searchQuery));
    setLastCheck(new Date());
    if (changes.length > 0) {
      setPriceChanges([...changes, ...priceChanges].slice(0, 50));
    }
  };

  // Filter products
  const filterProducts = (productList, category, query) => {
    return productList.filter(p => {
      const matchCategory = category === 'All' || p.category === category;
      const matchSearch = p.name.toLowerCase().includes(query.toLowerCase());
      return matchCategory && matchSearch;
    });
  };

  useEffect(() => {
    setFilteredProducts(filterProducts(products, selectedCategory, searchQuery));
  }, [selectedCategory, searchQuery, products]);

  // Add new product
  const addProduct = () => {
    if (!newProduct.name || !newProduct.url) return;

    const product = {
      id: Date.now(),
      ...newProduct,
      basePrice: 0,
      currentPrice: 0,
      priceHistory: [],
      lastChecked: new Date().toISOString(),
      priceChange: 0,
      changePercent: 0
    };

    setProducts([...products, product]);
    setNewProduct({ name: '', category: 'Laptops', url: '' });
    setShowAddForm(false);
  };

  // Calculate category trends
  const getCategoryTrends = () => {
    const trends = {};
    CATEGORIES.forEach(cat => {
      const catProducts = products.filter(p => p.category === cat);
      if (catProducts.length === 0) {
        trends[cat] = { avg: 0, change: 0, count: 0 };
        return;
      }

      const avgPrice = catProducts.reduce((sum, p) => sum + p.currentPrice, 0) / catProducts.length;
      const avgChange = catProducts.reduce((sum, p) => sum + parseFloat(p.changePercent || 0), 0) / catProducts.length;

      trends[cat] = {
        avg: Math.round(avgPrice),
        change: avgChange.toFixed(2),
        count: catProducts.length
      };
    });
    return trends;
  };

  const categoryTrends = getCategoryTrends();

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 text-slate-100 p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8 border-b border-amber-500/30 pb-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-4xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-amber-400 to-orange-500 mb-2">
                IT Price Sentinel
              </h1>
              <p className="text-slate-400 text-sm">Automated price tracking and trend analysis</p>
            </div>
            <button
              onClick={checkPrices}
              className="bg-gradient-to-r from-amber-600 to-orange-600 hover:from-amber-500 hover:to-orange-500 px-6 py-3 rounded-lg font-semibold flex items-center gap-2 shadow-lg shadow-amber-900/50 transition-all"
            >
              <Calendar className="w-5 h-5" />
              Run Price Check
            </button>
          </div>
          <div className="mt-4 flex items-center gap-2 text-sm text-slate-500">
            <Bell className="w-4 h-4" />
            Last checked: {lastCheck.toLocaleString()}
          </div>
        </div>

        {/* Statistics Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
          <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-4 backdrop-blur-sm">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-slate-400 text-sm">Total Products</p>
                <p className="text-3xl font-bold text-amber-400">{products.length}</p>
              </div>
              <Package className="w-10 h-10 text-amber-500/30" />
            </div>
          </div>

          <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-4 backdrop-blur-sm">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-slate-400 text-sm">Price Increases</p>
                <p className="text-3xl font-bold text-red-400">
                  {products.filter(p => p.priceChange > 0).length}
                </p>
              </div>
              <TrendingUp className="w-10 h-10 text-red-500/30" />
            </div>
          </div>

          <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-4 backdrop-blur-sm">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-slate-400 text-sm">Price Decreases</p>
                <p className="text-3xl font-bold text-green-400">
                  {products.filter(p => p.priceChange < 0).length}
                </p>
              </div>
              <TrendingDown className="w-10 h-10 text-green-500/30" />
            </div>
          </div>

          <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-4 backdrop-blur-sm">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-slate-400 text-sm">Recent Changes</p>
                <p className="text-3xl font-bold text-blue-400">{priceChanges.length}</p>
              </div>
              <BarChart3 className="w-10 h-10 text-blue-500/30" />
            </div>
          </div>
        </div>

        {/* Category Trends */}
        <div className="mb-8 bg-slate-800/50 border border-slate-700 rounded-lg p-6 backdrop-blur-sm">
          <h2 className="text-xl font-bold mb-4 text-amber-400 flex items-center gap-2">
            <BarChart3 className="w-5 h-5" />
            Category Trends
          </h2>
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-4">
            {CATEGORIES.map(cat => {
              const trend = categoryTrends[cat];
              const isPositive = trend.change > 0;
              const isNeutral = trend.change === 0;

              return (
                <div key={cat} className="bg-slate-900/50 rounded-lg p-4 border border-slate-600">
                  <p className="text-xs text-slate-400 mb-1">{cat}</p>
                  <p className="text-sm font-semibold text-slate-200 mb-2">
                    ${trend.avg.toLocaleString()}
                  </p>
                  <div className={`flex items-center gap-1 text-xs ${
                    isNeutral ? 'text-slate-400' : isPositive ? 'text-red-400' : 'text-green-400'
                  }`}>
                    {isNeutral ? <Minus className="w-3 h-3" /> :
                     isPositive ? <TrendingUp className="w-3 h-3" /> :
                     <TrendingDown className="w-3 h-3" />}
                    <span>{Math.abs(trend.change)}%</span>
                  </div>
                  <p className="text-xs text-slate-500 mt-1">{trend.count} items</p>
                </div>
              );
            })}
          </div>
        </div>

        {/* Controls */}
        <div className="mb-6 flex flex-wrap gap-4 items-center">
          <div className="flex-1 min-w-[200px]">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" />
              <input
                type="text"
                placeholder="Search products..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-10 pr-4 py-3 bg-slate-800 border border-slate-600 rounded-lg text-slate-100 placeholder-slate-500 focus:border-amber-500 focus:outline-none"
              />
            </div>
          </div>

          <select
            value={selectedCategory}
            onChange={(e) => setSelectedCategory(e.target.value)}
            className="px-4 py-3 bg-slate-800 border border-slate-600 rounded-lg text-slate-100 focus:border-amber-500 focus:outline-none"
          >
            <option value="All">All Categories</option>
            {CATEGORIES.map(cat => (
              <option key={cat} value={cat}>{cat}</option>
            ))}
          </select>

          <button
            onClick={() => setShowAddForm(!showAddForm)}
            className="bg-amber-600 hover:bg-amber-500 px-6 py-3 rounded-lg font-semibold flex items-center gap-2 transition-all"
          >
            <Plus className="w-5 h-5" />
            Add Product
          </button>
        </div>

        {/* Add Product Form */}
        {showAddForm && (
          <div className="mb-6 bg-slate-800/50 border border-amber-500/30 rounded-lg p-6 backdrop-blur-sm">
            <h3 className="text-lg font-bold mb-4 text-amber-400">Add New Product</h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <input
                type="text"
                placeholder="Product name"
                value={newProduct.name}
                onChange={(e) => setNewProduct({...newProduct, name: e.target.value})}
                className="px-4 py-2 bg-slate-900 border border-slate-600 rounded-lg text-slate-100 placeholder-slate-500 focus:border-amber-500 focus:outline-none"
              />
              <select
                value={newProduct.category}
                onChange={(e) => setNewProduct({...newProduct, category: e.target.value})}
                className="px-4 py-2 bg-slate-900 border border-slate-600 rounded-lg text-slate-100 focus:border-amber-500 focus:outline-none"
              >
                {CATEGORIES.map(cat => (
                  <option key={cat} value={cat}>{cat}</option>
                ))}
              </select>
              <input
                type="text"
                placeholder="Product URL"
                value={newProduct.url}
                onChange={(e) => setNewProduct({...newProduct, url: e.target.value})}
                className="px-4 py-2 bg-slate-900 border border-slate-600 rounded-lg text-slate-100 placeholder-slate-500 focus:border-amber-500 focus:outline-none"
              />
            </div>
            <div className="mt-4 flex gap-2">
              <button
                onClick={addProduct}
                className="bg-amber-600 hover:bg-amber-500 px-6 py-2 rounded-lg font-semibold transition-all"
              >
                Add Product
              </button>
              <button
                onClick={() => setShowAddForm(false)}
                className="bg-slate-700 hover:bg-slate-600 px-6 py-2 rounded-lg font-semibold transition-all"
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        {/* Product List */}
        <div className="bg-slate-800/50 border border-slate-700 rounded-lg overflow-hidden backdrop-blur-sm">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-slate-900/50">
                <tr>
                  <th className="text-left px-6 py-4 text-sm font-semibold text-amber-400">Product</th>
                  <th className="text-left px-6 py-4 text-sm font-semibold text-amber-400">Category</th>
                  <th className="text-right px-6 py-4 text-sm font-semibold text-amber-400">Current Price</th>
                  <th className="text-right px-6 py-4 text-sm font-semibold text-amber-400">Change</th>
                  <th className="text-left px-6 py-4 text-sm font-semibold text-amber-400">Last Checked</th>
                  <th className="text-center px-6 py-4 text-sm font-semibold text-amber-400">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-700">
                {filteredProducts.map(product => {
                  const isIncrease = product.priceChange > 0;
                  const isDecrease = product.priceChange < 0;
                  const hasChanged = Math.abs(product.priceChange) > 0;

                  return (
                    <tr
                      key={product.id}
                      className={`hover:bg-slate-700/30 transition-colors ${
                        hasChanged ? 'bg-slate-700/20' : ''
                      }`}
                    >
                      <td className="px-6 py-4">
                        <div>
                          <p className="font-semibold text-slate-100">{product.name}</p>
                          <p className="text-xs text-slate-500 truncate max-w-xs">{product.url}</p>
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <span className="px-3 py-1 bg-slate-700 rounded-full text-xs text-slate-300">
                          {product.category}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-right">
                        <p className="text-lg font-bold text-slate-100">
                          ${product.currentPrice.toLocaleString()}
                        </p>
                      </td>
                      <td className="px-6 py-4 text-right">
                        {hasChanged ? (
                          <div className={`flex items-center justify-end gap-1 ${
                            isIncrease ? 'text-red-400' : 'text-green-400'
                          }`}>
                            {isIncrease ? <TrendingUp className="w-4 h-4" /> : <TrendingDown className="w-4 h-4" />}
                            <span className="font-semibold">
                              {isIncrease ? '+' : ''}{product.priceChange > 0 ? product.priceChange : product.priceChange}
                            </span>
                            <span className="text-xs">({product.changePercent}%)</span>
                          </div>
                        ) : (
                          <div className="flex items-center justify-end gap-1 text-slate-500">
                            <Minus className="w-4 h-4" />
                            <span className="text-sm">No change</span>
                          </div>
                        )}
                      </td>
                      <td className="px-6 py-4 text-sm text-slate-400">
                        {new Date(product.lastChecked).toLocaleDateString()}
                      </td>
                      <td className="px-6 py-4 text-center">
                        <button
                          onClick={() => setSelectedProduct(selectedProduct?.id === product.id ? null : product)}
                          className="text-amber-400 hover:text-amber-300 font-semibold text-sm transition-colors"
                        >
                          {selectedProduct?.id === product.id ? 'Hide Chart' : 'View Chart'}
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>

        {/* Price History Chart */}
        {selectedProduct && selectedProduct.priceHistory.length > 0 && (
          <div className="mt-6 bg-slate-800/50 border border-slate-700 rounded-lg p-6 backdrop-blur-sm">
            <h3 className="text-lg font-bold mb-4 text-amber-400">
              Price History: {selectedProduct.name}
            </h3>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={selectedProduct.priceHistory}>
                <CartesianGrid strokeDasharray="3 3" stroke="#475569" />
                <XAxis
                  dataKey="date"
                  stroke="#94a3b8"
                  tick={{ fill: '#94a3b8' }}
                />
                <YAxis
                  stroke="#94a3b8"
                  tick={{ fill: '#94a3b8' }}
                  domain={['dataMin - 50', 'dataMax + 50']}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#1e293b',
                    border: '1px solid #475569',
                    borderRadius: '8px',
                    color: '#f1f5f9'
                  }}
                  formatter={(value) => [`$${value}`, 'Price']}
                />
                <Legend />
                <Line
                  type="monotone"
                  dataKey="price"
                  stroke="#f59e0b"
                  strokeWidth={2}
                  dot={{ fill: '#f59e0b', r: 4 }}
                  activeDot={{ r: 6 }}
                  name="Price"
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* Recent Price Changes */}
        {priceChanges.length > 0 && (
          <div className="mt-6 bg-slate-800/50 border border-slate-700 rounded-lg p-6 backdrop-blur-sm">
            <h3 className="text-lg font-bold mb-4 text-amber-400 flex items-center gap-2">
              <Bell className="w-5 h-5" />
              Recent Price Changes
            </h3>
            <div className="space-y-2 max-h-64 overflow-y-auto">
              {priceChanges.slice(0, 10).map((change, idx) => (
                <div
                  key={idx}
                  className="flex items-center justify-between p-3 bg-slate-900/50 rounded-lg"
                >
                  <div className="flex-1">
                    <p className="font-semibold text-slate-100">{change.productName}</p>
                    <p className="text-xs text-slate-500">
                      {new Date(change.timestamp).toLocaleString()}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm text-slate-400">
                      ${change.oldPrice} → ${change.newPrice}
                    </p>
                    <p className={`text-sm font-semibold ${
                      change.change > 0 ? 'text-red-400' : 'text-green-400'
                    }`}>
                      {change.change > 0 ? '+' : ''}{change.change} ({change.percent}%)
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
