import React, { useState, useEffect } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { TrendingUp, TrendingDown, Search, Plus, X, DollarSign, Package, ShoppingCart, Award, Trash2, Calendar, BarChart3 } from 'lucide-react';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:5001/api';

const CATEGORIES = ['Electronics', 'Laptops', 'Tablets', 'Monitors', 'Peripherals', 'Components', 'Storage', 'Networking'];

export default function PriceComparison() {
  const [groups, setGroups] = useState([]);
  const [products, setProducts] = useState([]);
  const [selectedGroup, setSelectedGroup] = useState(null);
  const [comparison, setComparison] = useState(null);
  const [showAddForm, setShowAddForm] = useState(false);
  const [loading, setLoading] = useState(false);
  const [searchForm, setSearchForm] = useState({
    query: '',
    category: 'Electronics'
  });
  const [searchResults, setSearchResults] = useState(null);
  const [selectedProducts, setSelectedProducts] = useState([]);
  const [selectedVariant, setSelectedVariant] = useState(null);
  const [selectedCategory, setSelectedCategory] = useState('All');
  const [searchQuery, setSearchQuery] = useState('');
  const [searchStage, setSearchStage] = useState('initial'); // 'initial', 'variant-selection', 'retailer-search'
  const [searchProgress, setSearchProgress] = useState({ show: false, stage: '', progress: 0, message: '' });
  const [priceHistory, setPriceHistory] = useState([]);

  // Fetch all product groups
  const fetchGroups = async () => {
    try {
      const res = await fetch(`${API_URL}/groups`);
      if (!res.ok) return;
      const data = await res.json();
      if (Array.isArray(data)) setGroups(data);
    } catch (err) {
      console.error('Failed to fetch groups:', err);
    }
  };

  // Fetch all products
  const fetchProducts = async () => {
    try {
      const res = await fetch(`${API_URL}/products`);
      if (!res.ok) return;
      const data = await res.json();
      if (Array.isArray(data)) setProducts(data);
    } catch (err) {
      console.error('Failed to fetch products:', err);
    }
  };

  // Fetch comparison for a specific group
  const fetchComparison = async (groupId) => {
    try {
      setPriceHistory([]);
      const res = await fetch(`${API_URL}/groups/${groupId}`);
      if (!res.ok) {
        setComparison(null);
        return;
      }
      const data = await res.json();
      if (data && data.group) {
        setComparison(data);
        fetchGroupPriceHistory(data);
      } else {
        setComparison(null);
      }
    } catch (err) {
      console.error('Failed to fetch comparison:', err);
      setComparison(null);
    }
  };

  useEffect(() => {
    fetchGroups();
    fetchProducts();
  }, []);

  // Fetch price history for all products in a group and merge into chart data
  const fetchGroupPriceHistory = async (comparisonData) => {
    if (!comparisonData?.products?.length) {
      setPriceHistory([]);
      return;
    }

    try {
      // Fetch history for each product in parallel
      const historyPromises = comparisonData.products.map(async (product) => {
        const res = await fetch(`${API_URL}/products/${product.id}/history?days=30`);
        const history = await res.json();
        return { retailer: product.retailer, history };
      });

      const allHistory = await Promise.all(historyPromises);

      // Merge into a single dataset keyed by date
      const dateMap = {};
      for (const { retailer, history } of allHistory) {
        for (const entry of history) {
          const date = entry.timestamp.split('T')[0].split(' ')[0]; // Get YYYY-MM-DD
          if (!dateMap[date]) {
            dateMap[date] = { date };
          }
          dateMap[date][retailer] = entry.price;
        }
      }

      // Sort by date and fill forward missing values
      const sorted = Object.values(dateMap).sort((a, b) => a.date.localeCompare(b.date));

      // Fill forward: if a retailer has no entry for a date, use last known price
      const retailers = comparisonData.products.map(p => p.retailer);
      const lastKnown = {};
      for (const row of sorted) {
        for (const retailer of retailers) {
          if (row[retailer] != null) {
            lastKnown[retailer] = row[retailer];
          } else if (lastKnown[retailer] != null) {
            row[retailer] = lastKnown[retailer];
          }
        }
      }

      setPriceHistory(sorted);
    } catch (err) {
      console.error('Failed to fetch price history:', err);
      setPriceHistory([]);
    }
  };

  useEffect(() => {
    if (selectedGroup) {
      fetchComparison(selectedGroup.id);
    }
  }, [selectedGroup]);

  // Filter products
  const filteredProducts = products.filter(p => {
    const matchCategory = selectedCategory === 'All' || p.category === selectedCategory;
    const matchSearch = p.name?.toLowerCase().includes(searchQuery.toLowerCase());
    return matchCategory && matchSearch;
  });

  // Calculate category trends
  const getCategoryTrends = () => {
    const trends = {};
    CATEGORIES.forEach(cat => {
      const catProducts = products.filter(p => p.category === cat);
      if (catProducts.length === 0) {
        trends[cat] = { avg: 0, count: 0 };
        return;
      }

      const avgPrice = catProducts.reduce((sum, p) => sum + (p.current_price || 0), 0) / catProducts.length;

      trends[cat] = {
        avg: Math.round(avgPrice),
        count: catProducts.length
      };
    });
    return trends;
  };

  const categoryTrends = getCategoryTrends();

  // Stage 1: Search and show variants for selection
  const handleSearchPreview = async () => {
    if (!searchForm.query) {
      alert('Please enter a product name');
      return;
    }

    setLoading(true);
    setSearchResults(null);
    setSelectedProducts([]);
    setSelectedVariant(null);
    setSearchStage('variant-selection');

    // Show progress modal
    const startTime = Date.now();
    setSearchProgress({ show: true, stage: 'Searching PriceSpy NZ...', progress: 10, message: 'Finding retailers' });

    console.log('🔍 Stage 1: Searching for variants of:', searchForm.query);

    // Smooth progress animation with stage labels
    const stages = [
      { at: 15, stage: 'Connecting to retailers...', message: 'Launching browser sessions' },
      { at: 30, stage: 'Searching PBTech...', message: 'Scanning retailer catalogue' },
      { at: 45, stage: 'Searching Noel Leeming...', message: 'Extracting product data' },
      { at: 60, stage: 'Searching JB Hi-Fi...', message: 'Comparing product listings' },
      { at: 75, stage: 'Searching Acquire...', message: 'Gathering final results' },
      { at: 88, stage: 'Processing results...', message: 'Almost done' },
    ];
    const progressInterval = setInterval(() => {
      setSearchProgress(prev => {
        if (prev.progress >= 90) return prev;
        const next = prev.progress + 1;
        const currentStage = [...stages].reverse().find(s => next >= s.at);
        return {
          show: true,
          progress: next,
          stage: currentStage?.stage || prev.stage,
          message: currentStage?.message || prev.message,
        };
      });
    }, 600);

    try {
      const res = await fetch(`${API_URL}/search-preview`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: searchForm.query, category: searchForm.category })
      });

      clearInterval(progressInterval);

      setSearchProgress({ progress: 95, stage: 'Processing results...', message: 'Deduplicating products', show: true });

      const data = await res.json();

      if (data.success) {
        setSearchProgress({ progress: 100, stage: '✅ Search Complete!', message: `Found ${data.products?.length || 0} products from multiple retailers`, show: true });
        console.log(`✅ Found ${data.products?.length || 0} total results`);

        // Deduplicate by product identity (model tier + storage size)
        // e.g., "iPhone 17 256GB" and "iPhone 17 512GB" are DIFFERENT products
        //        "iPhone 17 256GB" from PBTech and Noel Leeming are the SAME product

        const TIER_WORDS = ['pro', 'max', 'plus', 'ultra', 'mini', 'lite', 'se', 'air'];
        const COLOR_WORDS = ['black', 'white', 'silver', 'gold', 'grey', 'gray', 'blue', 'red', 'green', 'pink', 'purple', 'midnight', 'starlight', 'titanium', 'graphite', 'space'];

        const getProductIdentityKey = (product) => {
          // If we have a retailer-specific model number, use it directly
          if (product.model && product.model.trim()) {
            return product.model.toLowerCase().trim();
          }

          // Otherwise, build a normalized key from the product name
          const name = product.name.toLowerCase();

          // Extract storage size (e.g., "256gb", "512gb", "1tb", "2tb")
          const storageMatch = name.match(/(\d+\s*[gt]b)/i);
          const storage = storageMatch ? storageMatch[1].replace(/\s/g, '') : '';

          // Extract tier words
          const words = name.split(/[\s\-\/,]+/);
          const tiers = words.filter(w => TIER_WORDS.includes(w)).sort().join('-');

          // Extract core product words (not color, not common filler)
          const coreWords = words.filter(w =>
            w.length > 1 &&
            !COLOR_WORDS.includes(w) &&
            !TIER_WORDS.includes(w) &&
            !['the', 'and', 'with', 'for', 'in', 'new', 'nz', 'wifi', 'wi-fi'].includes(w) &&
            !/^\d+\s*[gt]b$/i.test(w) // exclude storage (already captured)
          ).slice(0, 4).join('-');

          return [coreWords, tiers, storage].filter(Boolean).join('|');
        };

        const uniqueProducts = [];
        const seen = new Set();

        for (const product of data.products) {
          const key = getProductIdentityKey(product);
          console.log(`  Dedup key: "${key}" ← ${product.retailer}: ${product.name}`);

          if (!seen.has(key)) {
            seen.add(key);
            uniqueProducts.push(product);
          }
        }

        console.log(`✅ Showing ${uniqueProducts.length} unique products`);

        // Store both unique and all products
        setSearchResults({
          ...data,
          products: uniqueProducts,
          allProducts: data.products  // Keep all for matching later
        });

        // Ensure minimum display time (3 seconds)
        const elapsed = Date.now() - startTime;
        const minDisplayTime = 3000;
        const remainingTime = Math.max(0, minDisplayTime - elapsed);

        setTimeout(() => {
          setSearchProgress({ show: false, stage: '', progress: 0, message: '' });
        }, remainingTime + 800); // Extra 800ms to show "Complete!" message
      } else {
        console.error('❌ Search failed:', data.error);
        setSearchProgress({ show: false, stage: '', progress: 0, message: '' });
        alert(`❌ ${data.error}`);
      }
    } catch (err) {
      console.error('❌ Search error:', err);
      clearInterval(progressInterval);
      setSearchProgress({ show: false, stage: '', progress: 0, message: '' });
      alert(`Search failed: ${err.message}`);
    }
    setLoading(false);
  };

  // Stage 2: Find all retailers selling the selected product
  const handleVariantSelected = async (variantIndex) => {
    const variant = searchResults.products[variantIndex];
    setSelectedVariant(variant);
    setLoading(true);

    console.log('✅ Selected product:', variant.name);
    console.log('Model:', variant.model || 'N/A');
    console.log('🔍 Finding ALL retailers selling this product...');

    // Search through ALL products (not just unique ones) to find all retailers
    const allProducts = searchResults.allProducts || searchResults.products;
    let matchingProducts = [];

    // Strategy 1: Match by model number (most accurate)
    if (variant.model && variant.model.trim() !== '') {
      console.log(`\n🎯 Searching by model number: ${variant.model}`);

      matchingProducts = allProducts.filter(p => {
        if (p.model && p.model.trim() !== '') {
          const isMatch = p.model.toLowerCase() === variant.model.toLowerCase();
          if (isMatch) {
            console.log(`  ✅ Model match: ${p.retailer} - ${p.name} (${p.model})`);
          }
          return isMatch;
        }
        return false;
      });

      console.log(`Found ${matchingProducts.length} products with model ${variant.model}`);
    }

    // Strategy 2: If no model matches, fall back to fuzzy name matching
    if (matchingProducts.length === 0) {
      console.log('\n⚠️  No model number available or no matches found');
      console.log('📝 Using fuzzy name matching instead...');

      // Words that distinguish product tiers - mismatch on these means different product
      const TIER_WORDS = new Set(['pro', 'max', 'plus', 'ultra', 'mini', 'lite', 'se', 'air', 'standard', 'basic']);

      // Extract key identifying words from the product name
      const extractKeyWords = (name) => {
        const words = name.toLowerCase()
          .replace(/[()]/g, '')
          .split(/[\s-]+/)
          .filter(word =>
            word.length > 0 &&
            !['the', 'and', 'with', 'for', 'in'].includes(word)
          );
        return new Set(words);
      };

      // Extract tier words present in a name
      const extractTierWords = (name) => {
        const words = name.toLowerCase().split(/[\s-]+/);
        return new Set(words.filter(w => TIER_WORDS.has(w)));
      };

      const variantKeyWords = extractKeyWords(variant.name);
      const variantTierWords = extractTierWords(variant.name);
      console.log('Key words:', Array.from(variantKeyWords).join(', '));
      console.log('Tier words:', Array.from(variantTierWords).join(', ') || '(none)');

      matchingProducts = allProducts.filter(p => {
        const productKeyWords = extractKeyWords(p.name);
        const productTierWords = extractTierWords(p.name);

        // Tier words must match exactly - "iPhone 17" must NOT match "iPhone 17 Pro"
        const variantTierStr = Array.from(variantTierWords).sort().join(',');
        const productTierStr = Array.from(productTierWords).sort().join(',');
        if (variantTierStr !== productTierStr) {
          console.log(`  ❌ Tier mismatch: "${variantTierStr}" vs "${productTierStr}": ${p.retailer} - ${p.name}`);
          return false;
        }

        // All variant keywords must appear in the product name
        const missingWords = [...variantKeyWords].filter(w => !productKeyWords.has(w));
        if (missingWords.length > 0) {
          // Allow minor mismatches for config words (colour, storage) but not model identifiers
          const significantMissing = missingWords.filter(w => w.length > 3 || /\d/.test(w));
          if (significantMissing.length > 0) {
            console.log(`  ❌ Missing keywords [${significantMissing.join(', ')}]: ${p.retailer} - ${p.name}`);
            return false;
          }
        }

        // Check overall similarity (at least 50% overlap both ways)
        const intersection = new Set([...variantKeyWords].filter(x => productKeyWords.has(x)));
        const similarity = intersection.size / Math.max(variantKeyWords.size, productKeyWords.size);

        if (similarity >= 0.4) {
          console.log(`  ✅ Match (${(similarity * 100).toFixed(0)}%): ${p.retailer} - ${p.name}`);
          return true;
        } else {
          console.log(`  ❌ Low similarity (${(similarity * 100).toFixed(0)}%): ${p.retailer} - ${p.name}`);
          return false;
        }
      });
    }

    console.log(`\n✅ Found ${matchingProducts.length} retailers selling this product`);

    // Show user what will be added
    if (matchingProducts.length === 0) {
      alert('❌ No matching products found. Try a different variant.');
      setLoading(false);
      return;
    }

    const retailerList = matchingProducts.map(p => `${p.retailer}: $${p.price.toFixed(2)}`).join('\n');
    const confirmed = confirm(`Add ${matchingProducts.length} products?\n\n${retailerList}`);

    if (!confirmed) {
      setLoading(false);
      return;
    }

    // Add all matching retailers
    try {
      const res = await fetch(`${API_URL}/products/add-selected`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          products: matchingProducts,
          category: searchForm.category
        })
      });

      const data = await res.json();

      if (data.success) {
        alert(`✅ Added ${data.added} products from ${matchingProducts.length} retailers!`);
        fetchGroups();
        fetchProducts();
        setShowAddForm(false);
        setSearchForm({ query: '', category: 'Electronics' });
        setSearchResults(null);
        setSelectedProducts([]);
        setSelectedVariant(null);
        setSearchStage('initial');
      } else {
        alert(`❌ ${data.error}`);
      }
    } catch (err) {
      alert('Failed to add products');
    }
    setLoading(false);
  };

  // Add selected products to database
  const handleAddSelected = async () => {
    if (selectedProducts.length === 0) {
      alert('Please select at least one retailer');
      return;
    }

    setLoading(true);
    try {
      const productsToAdd = selectedProducts.map(idx => searchResults.products[idx]);

      const res = await fetch(`${API_URL}/products/add-selected`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          products: productsToAdd,
          category: searchForm.category
        })
      });

      const data = await res.json();

      if (data.success) {
        alert(`✅ Added ${data.added} products from ${selectedProducts.length} retailers!`);
        fetchGroups();
        fetchProducts();
        setShowAddForm(false);
        setSearchForm({ query: '', category: 'Electronics' });
        setSearchResults(null);
        setSelectedProducts([]);
        setSelectedVariant(null);
        setSearchStage('initial');
      } else {
        alert(`❌ ${data.error}`);
      }
    } catch (err) {
      alert('Failed to add products');
    }
    setLoading(false);
  };

  const toggleProductSelection = (index) => {
    setSelectedProducts(prev =>
      prev.includes(index)
        ? prev.filter(i => i !== index)
        : [...prev, index]
    );
  };

  // Delete an individual product
  const handleDeleteProduct = async (productId) => {
    if (!confirm('Delete this product listing?')) {
      return;
    }

    try {
      const res = await fetch(`${API_URL}/products/${productId}`, {
        method: 'DELETE'
      });

      const data = await res.json();

      if (data.success) {
        alert('✅ Product deleted');
        fetchProducts();
        fetchGroups();
      } else {
        alert(`❌ ${data.error}`);
      }
    } catch (err) {
      console.error('Delete error:', err);
      alert('Failed to delete product');
    }
  };

  // Delete a product group
  const handleDeleteGroup = async (groupId) => {
    if (!confirm('Delete this product and all its retailer listings?')) {
      return;
    }

    try {
      const res = await fetch(`${API_URL}/groups/${groupId}`, {
        method: 'DELETE'
      });

      const data = await res.json();

      if (data.success) {
        alert('✅ Product group deleted');
        fetchGroups();
        fetchProducts();
        if (selectedGroup?.id === groupId) {
          setSelectedGroup(null);
          setComparison(null);
        }
      } else {
        alert(`❌ ${data.error}`);
      }
    } catch (err) {
      console.error('Delete error:', err);
      alert('Failed to delete group');
    }
  };

  // Check prices for all products
  const handleCheckPrices = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/check-prices`, {
        method: 'POST'
      });
      const data = await res.json();
      alert(`✅ Checked ${data.checked} products\n${data.updated} prices updated`);
      fetchGroups();
      if (selectedGroup) {
        fetchComparison(selectedGroup.id);
      }
    } catch (err) {
      alert('Failed to check prices');
    }
    setLoading(false);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 text-slate-100 p-6">
      {/* Progress Modal */}
      {searchProgress.show && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50">
          <div className="bg-slate-800 border border-amber-500/30 rounded-lg p-8 max-w-md w-full mx-4 shadow-2xl">
            <div className="text-center">
              <div className="mb-4">
                <div className="inline-flex items-center justify-center w-16 h-16 bg-amber-600/20 rounded-full mb-4">
                  <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-amber-500"></div>
                </div>
              </div>
              <h3 className="text-xl font-bold text-amber-400 mb-2">{searchProgress.stage}</h3>
              <p className="text-slate-400 text-sm mb-4">{searchProgress.message}</p>

              {/* Progress Bar */}
              <div className="w-full bg-slate-700 rounded-full h-3 mb-2 overflow-hidden">
                <div
                  className="bg-gradient-to-r from-amber-600 to-orange-600 h-full rounded-full transition-all duration-500 ease-out"
                  style={{ width: `${searchProgress.progress}%` }}
                ></div>
              </div>
              <p className="text-slate-500 text-xs">{searchProgress.progress}% complete</p>
            </div>
          </div>
        </div>
      )}

      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8 border-b border-amber-500/30 pb-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-4xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-amber-400 to-orange-500 mb-2">
                Multi-Retailer Price Tracker
              </h1>
              <p className="text-slate-400 text-sm">Compare prices across all retailers instantly</p>
            </div>
            <div className="flex gap-3">
              <button
                onClick={handleCheckPrices}
                disabled={loading}
                className="bg-blue-600 hover:bg-blue-500 px-6 py-3 rounded-lg font-semibold flex items-center gap-2 disabled:opacity-50"
              >
                {loading ? '⏳' : '🔄'} Check Prices
              </button>
              <button
                onClick={() => setShowAddForm(!showAddForm)}
                className="bg-gradient-to-r from-amber-600 to-orange-600 hover:from-amber-500 hover:to-orange-500 px-6 py-3 rounded-lg font-semibold flex items-center gap-2"
              >
                <Plus className="w-5 h-5" />
                Add Product
              </button>
            </div>
          </div>
        </div>

        {/* Statistics */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
          <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-slate-400 text-sm">Products Tracked</p>
                <p className="text-3xl font-bold text-amber-400">{products.length}</p>
              </div>
              <Package className="w-10 h-10 text-amber-500/30" />
            </div>
          </div>

          <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-slate-400 text-sm">Product Groups</p>
                <p className="text-3xl font-bold text-blue-400">{groups.length}</p>
              </div>
              <ShoppingCart className="w-10 h-10 text-blue-500/30" />
            </div>
          </div>

          <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-slate-400 text-sm">Total Retailers</p>
                <p className="text-3xl font-bold text-purple-400">
                  {new Set(products.map(p => p.retailer)).size}
                </p>
              </div>
              <Award className="w-10 h-10 text-purple-500/30" />
            </div>
          </div>

          <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-slate-400 text-sm">Avg Price Variance</p>
                <p className="text-3xl font-bold text-green-400">
                  {(() => {
                    const validGroups = groups.filter(g => g.min_price && g.max_price && g.min_price !== g.max_price);
                    if (validGroups.length === 0) return '0.0';
                    const totalVariance = validGroups.reduce((sum, g) => {
                      const avg = (g.min_price + g.max_price) / 2;
                      return sum + ((g.max_price - g.min_price) / avg * 100);
                    }, 0);
                    return (totalVariance / validGroups.length).toFixed(1);
                  })()}%
                </p>
              </div>
              <TrendingUp className="w-10 h-10 text-green-500/30" />
            </div>
          </div>
        </div>

        {/* Category Trends */}
        {products.length > 0 && (
          <div className="mb-8 bg-slate-800/50 border border-slate-700 rounded-lg p-6 backdrop-blur-sm">
            <h2 className="text-xl font-bold mb-4 text-amber-400 flex items-center gap-2">
              <BarChart3 className="w-5 h-5" />
              Category Overview
            </h2>
            <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-8 gap-4">
              {CATEGORIES.map(cat => {
                const trend = categoryTrends[cat];

                return (
                  <div key={cat} className="bg-slate-900/50 rounded-lg p-4 border border-slate-600">
                    <p className="text-xs text-slate-400 mb-1">{cat}</p>
                    <p className="text-sm font-semibold text-slate-200 mb-2">
                      ${trend.avg.toLocaleString()}
                    </p>
                    <p className="text-xs text-slate-500">{trend.count} items</p>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Add Product Form */}
        {showAddForm && (
          <div className="mb-6 bg-slate-800/50 border border-amber-500/30 rounded-lg p-6 backdrop-blur-sm">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-bold text-amber-400">
                {searchStage === 'initial' && 'Search All Retailers'}
                {searchStage === 'variant-selection' && 'Select Product to Track'}
              </h3>
              <button onClick={() => {
                setShowAddForm(false);
                setSearchResults(null);
                setSelectedProducts([]);
                setSelectedVariant(null);
                setSearchStage('initial');
              }}>
                <X className="w-5 h-5" />
              </button>
            </div>

            {searchStage === 'initial' && (
              <>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                  <input
                    type="text"
                    placeholder="Product name (e.g., Lenovo Thinkbook)"
                    value={searchForm.query}
                    onChange={(e) => setSearchForm({...searchForm, query: e.target.value})}
                    onKeyPress={(e) => e.key === 'Enter' && handleSearchPreview()}
                    className="px-4 py-2 bg-slate-900 border border-slate-600 rounded-lg text-slate-100 placeholder-slate-500 focus:border-amber-500 focus:outline-none"
                  />
                  <select
                    value={searchForm.category}
                    onChange={(e) => setSearchForm({...searchForm, category: e.target.value})}
                    className="px-4 py-2 bg-slate-900 border border-slate-600 rounded-lg text-slate-100 focus:border-amber-500 focus:outline-none"
                  >
                    <option>Electronics</option>
                    <option>Laptops</option>
                    <option>Tablets</option>
                    <option>Monitors</option>
                    <option>Peripherals</option>
                  </select>
                </div>
                <button
                  onClick={handleSearchPreview}
                  disabled={loading}
                  className="bg-amber-600 hover:bg-amber-500 px-6 py-2 rounded-lg font-semibold disabled:opacity-50"
                >
                  {loading ? '🔍 Searching...' : '🔍 Find Products'}
                </button>
                <p className="text-xs text-slate-500 mt-2">
                  Search all retailers • Click a product to track it across all stores
                </p>
              </>
            )}

            {searchStage === 'variant-selection' && searchResults && (
              <>
                <div className="mb-4 p-3 bg-blue-600/20 border border-blue-500/30 rounded-lg">
                  <p className="text-sm text-blue-300">
                    💡 Click any product below to automatically track it across ALL retailers
                  </p>
                </div>

                <p className="text-sm text-slate-400 mb-4">
                  Found {searchResults.products.length} unique products. Select one to track across all retailers:
                </p>

                {/* Product Selection - Unique products only */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6 max-h-96 overflow-y-auto">
                  {searchResults.products.map((product, idx) => (
                    <div
                      key={idx}
                      onClick={() => handleVariantSelected(idx)}
                      className="p-4 rounded-lg border-2 cursor-pointer transition-all border-slate-600 bg-slate-700/30 hover:border-amber-500 hover:bg-amber-500/10"
                    >
                      <div className="flex items-start gap-3">
                        <div className="flex-1">
                          <h4 className="text-lg font-semibold text-slate-100 mb-2">
                            {product.name}
                          </h4>
                          <div className="flex items-center gap-3 text-sm text-slate-400">
                            {product.brand && (
                              <span>Brand: {product.brand}</span>
                            )}
                            {product.model && (
                              <span className="px-2 py-1 bg-purple-600/20 text-purple-400 rounded text-xs">
                                Model: {product.model}
                              </span>
                            )}
                          </div>
                          <div className="mt-2 text-lg font-bold text-green-400">
                            From ${product.price.toFixed(2)}
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>

                <button
                  onClick={() => {
                    setSearchResults(null);
                    setSearchStage('initial');
                  }}
                  className="bg-slate-600 hover:bg-slate-500 px-6 py-2 rounded-lg font-semibold"
                >
                  ← Back to Search
                </button>
              </>
            )}
          </div>
        )}

        {/* Search and Filter Controls */}
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
        </div>

        {/* Product Table */}
        <div className="bg-slate-800/50 border border-slate-700 rounded-lg overflow-hidden backdrop-blur-sm">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-slate-900/50">
                <tr>
                  <th className="text-left px-6 py-4 text-sm font-semibold text-amber-400">Product</th>
                  <th className="text-left px-6 py-4 text-sm font-semibold text-amber-400">Retailer</th>
                  <th className="text-left px-6 py-4 text-sm font-semibold text-amber-400">Category</th>
                  <th className="text-right px-6 py-4 text-sm font-semibold text-amber-400">Current Price</th>
                  <th className="text-left px-6 py-4 text-sm font-semibold text-amber-400">Last Checked</th>
                  <th className="text-center px-6 py-4 text-sm font-semibold text-amber-400">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-700">
                {filteredProducts.map(product => (
                  <tr
                    key={product.id}
                    className="hover:bg-slate-700/30 transition-colors"
                  >
                    <td className="px-6 py-4">
                      <div>
                        <p className="font-semibold text-slate-100">{product.name}</p>
                        <p className="text-xs text-slate-500 truncate max-w-xs">{product.url}</p>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <span className="px-3 py-1 bg-blue-600/20 text-blue-400 rounded-full text-xs font-medium">
                        {product.retailer}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <span className="px-3 py-1 bg-slate-700 rounded-full text-xs text-slate-300">
                        {product.category}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-right">
                      <p className="text-lg font-bold text-green-400">
                        ${product.current_price?.toFixed(2)}
                      </p>
                    </td>
                    <td className="px-6 py-4 text-sm text-slate-400">
                      {product.last_checked ? new Date(product.last_checked).toLocaleString() : 'Never'}
                    </td>
                    <td className="px-6 py-4 text-center">
                      <div className="flex items-center justify-center gap-2">
                        <a
                          href={product.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-amber-400 hover:text-amber-300 font-semibold text-sm transition-colors"
                        >
                          View
                        </a>
                        <button
                          onClick={() => handleDeleteProduct(product.id)}
                          className="text-red-400 hover:text-red-300 font-semibold text-sm transition-colors"
                          title="Delete product"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
                {filteredProducts.length === 0 && (
                  <tr>
                    <td colSpan="6" className="px-6 py-12 text-center">
                      <div className="text-slate-500">
                        <Package className="w-12 h-12 mx-auto mb-2 opacity-50" />
                        <p>No products found</p>
                        <p className="text-sm">Try adjusting your search or add new products</p>
                      </div>
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Product Groups Section */}
        <div className="mt-8 bg-slate-800/50 border border-slate-700 rounded-lg p-6 backdrop-blur-sm">
          <h2 className="text-xl font-bold mb-4 text-amber-400 flex items-center gap-2">
            <BarChart3 className="w-5 h-5" />
            Product Groups & Price Comparison
          </h2>
          {groups.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {groups.map(group => (
                <div
                  key={group.id}
                  onClick={() => setSelectedGroup(group)}
                  className={`p-4 rounded-lg transition-all cursor-pointer ${
                    selectedGroup?.id === group.id
                      ? 'bg-amber-600/20 border-2 border-amber-500'
                      : 'bg-slate-700/30 border border-slate-600 hover:bg-slate-700/50'
                  }`}
                >
                  <h3 className="font-semibold text-slate-100 mb-1">{group.name}</h3>
                  <p className="text-xs text-slate-400 mb-2">Model: {group.model}</p>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-slate-400">
                      {group.retailer_count} retailers
                    </span>
                    {group.min_price && (
                      <div className="text-right">
                        <div className="text-sm font-semibold text-blue-400">
                          ${group.min_price?.toFixed(2)} - ${group.max_price?.toFixed(2)}
                        </div>
                        {group.max_price - group.min_price > 0 && (
                          <div className="text-xs text-slate-500">
                            {(((group.max_price - group.min_price) / group.min_price) * 100).toFixed(1)}% spread
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-8">
              <Package className="w-10 h-10 mx-auto mb-2 text-slate-500 opacity-50" />
              <p className="text-slate-400">No product groups yet</p>
              <p className="text-sm text-slate-500">Add a product to create your first price comparison group</p>
            </div>
          )}
        </div>

        {/* Comparison View */}
        {selectedGroup && !comparison && (
          <div className="mt-8 bg-slate-800/50 border border-slate-700 rounded-lg p-6 backdrop-blur-sm text-center">
            <DollarSign className="w-10 h-10 mx-auto mb-2 text-slate-500 opacity-50" />
            <p className="text-slate-400">No comparison data available for this group</p>
            <p className="text-sm text-slate-500">The group may have been deleted or has no products</p>
          </div>
        )}
        {comparison && (
          <div className="mt-8 space-y-6">
            {/* Product Info */}
            <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-6 backdrop-blur-sm">
              <h2 className="text-2xl font-bold text-amber-400 mb-2">
                {comparison.group.name}
              </h2>
              <div className="flex gap-4 text-sm text-slate-400">
                <span>Model: {comparison.group.model}</span>
                <span>Brand: {comparison.group.brand}</span>
                <span>Category: {comparison.group.category}</span>
              </div>
            </div>

            {/* Price Comparison Bars */}
            <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-6 backdrop-blur-sm">
              <h3 className="text-lg font-bold text-amber-400 mb-4">💰 Price Comparison</h3>
              <div className="space-y-3">
                {comparison.products.map(product => {
                  const isCheapest = product.id === comparison.cheapest?.id;
                  const percentage = (product.current_price / comparison.most_expensive.current_price) * 100;

                  return (
                    <div key={product.id} className="relative">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-sm font-semibold text-slate-200 flex items-center gap-2">
                          {product.retailer}
                          {isCheapest && <Award className="w-4 h-4 text-yellow-400" />}
                        </span>
                        <span className="text-lg font-bold text-slate-100">
                          ${product.current_price?.toFixed(2)}
                        </span>
                      </div>
                      <div className="h-8 bg-slate-700/50 rounded-lg overflow-hidden">
                        <div
                          className={`h-full flex items-center px-3 transition-all ${
                            isCheapest
                              ? 'bg-gradient-to-r from-green-600 to-green-500'
                              : 'bg-gradient-to-r from-slate-600 to-slate-500'
                          }`}
                          style={{ width: `${percentage}%` }}
                        >
                          {isCheapest && (
                            <span className="text-xs font-semibold text-white">
                              🏆 Best Price
                            </span>
                          )}
                        </div>
                      </div>
                      <a
                        href={product.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs text-blue-400 hover:text-blue-300 mt-1 inline-block"
                      >
                        View on {product.retailer} →
                      </a>
                    </div>
                  );
                })}
              </div>

              {/* Price Spread Analysis */}
              {comparison.price_range > 0 && (
                <div className="mt-6 p-4 bg-purple-600/20 border border-purple-500/30 rounded-lg">
                  <div className="grid grid-cols-3 gap-4">
                    <div>
                      <p className="text-sm text-purple-300">📊 Price Spread</p>
                      <p className="text-2xl font-bold text-purple-400">
                        ${comparison.price_range.toFixed(2)}
                      </p>
                    </div>
                    <div>
                      <p className="text-sm text-purple-300">📈 Variance</p>
                      <p className="text-2xl font-bold text-purple-400">
                        {((comparison.price_range / comparison.cheapest.current_price) * 100).toFixed(1)}%
                      </p>
                    </div>
                    <div className="text-right">
                      <p className="text-sm text-slate-300">Lowest Price</p>
                      <p className="text-lg font-semibold text-green-400">
                        {comparison.cheapest.retailer}
                      </p>
                      <p className="text-sm text-slate-400">
                        ${comparison.cheapest.current_price.toFixed(2)}
                      </p>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Price History Chart */}
            <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-6 backdrop-blur-sm">
              <h3 className="text-lg font-bold text-amber-400 mb-4">
                <Calendar className="w-5 h-5 inline mr-2" />
                Price History
              </h3>
              {priceHistory.length > 1 ? (
                <>
                  <ResponsiveContainer width="100%" height={350}>
                    <LineChart
                      data={priceHistory}
                      margin={{ top: 20, right: 30, left: 20, bottom: 5 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" stroke="#475569" />
                      <XAxis
                        dataKey="date"
                        stroke="#94a3b8"
                        tick={{ fill: '#94a3b8', fontSize: 12 }}
                        tickFormatter={(date) => {
                          const d = new Date(date);
                          return `${d.getDate()}/${d.getMonth() + 1}`;
                        }}
                      />
                      <YAxis
                        stroke="#94a3b8"
                        tick={{ fill: '#94a3b8' }}
                        domain={['dataMin - 50', 'dataMax + 50']}
                        tickFormatter={(value) => `$${value}`}
                      />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: '#1e293b',
                          border: '1px solid #475569',
                          borderRadius: '8px',
                          color: '#f1f5f9'
                        }}
                        formatter={(value) => [`$${Number(value).toFixed(2)}`, '']}
                        labelFormatter={(date) => {
                          const d = new Date(date);
                          return d.toLocaleDateString('en-NZ', { day: 'numeric', month: 'short', year: 'numeric' });
                        }}
                      />
                      <Legend />
                      {comparison.products.map((product, index) => {
                        const colors = ['#f59e0b', '#3b82f6', '#10b981', '#a855f7', '#ef4444'];
                        return (
                          <Line
                            key={product.id}
                            type="monotone"
                            dataKey={product.retailer}
                            name={product.retailer}
                            stroke={colors[index % colors.length]}
                            strokeWidth={2}
                            dot={{ fill: colors[index % colors.length], r: 4 }}
                            activeDot={{ r: 6 }}
                            connectNulls
                          />
                        );
                      })}
                    </LineChart>
                  </ResponsiveContainer>
                  <p className="text-xs text-slate-500 mt-2">Last 30 days of price data</p>
                </>
              ) : (
                <div className="text-center py-8">
                  <Calendar className="w-8 h-8 mx-auto mb-2 text-slate-500" />
                  <p className="text-slate-400">Price history will appear here after multiple price checks</p>
                  <p className="text-xs text-slate-500 mt-1">Run "Check Prices" periodically to build history data</p>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
