import React, { useState } from 'react';
import { 
  Camera, Mail, Phone, ChevronRight, User, Users, 
  LogOut, KeyRound, Check, Plus, Trash2
} from 'lucide-react';

export default function ProfilePage({ user, onNavigate, onLogout, t }) {
  // Active Sidebar Menu: 'profile' | 'travelers' | 'reset-password'
  const [activeMenu, setActiveMenu] = useState('profile');

  // General Information State (No marital status, No anniversary, No passport, No pancard, No ID proof)
  const [formData, setFormData] = useState({
    firstName: user?.name ? user.name.split(' ')[0] : 'Elena',
    lastName: user?.name ? user.name.split(' ').slice(1).join(' ') || 'Vance' : 'Vance',
    age: '31',
    gender: 'Female',
    nationality: 'Indian',
    city: 'Mumbai',
    state: 'Maharashtra',
    phone: '+91 98201 48219',
    email: user?.email || 'elena.vance@voyage.io'
  });

  const [confirmCity, setConfirmCity] = useState('Mumbai');
  const [saveToast, setSaveToast] = useState(false);

  // Co-Travellers (Simple List with just Full Name, Age & Gender as requested)
  const [coTravellers, setCoTravellers] = useState([
    { id: 1, name: 'Marcus Vance', age: 35, gender: 'Male' },
    { id: 2, name: 'Sophia Vance', age: 8, gender: 'Female' },
    { id: 3, name: 'Rohan Sharma', age: 29, gender: 'Male' }
  ]);

  const [newTraveller, setNewTraveller] = useState({ name: '', age: '', gender: 'Male' });
  const [showAddModal, setShowAddModal] = useState(false);

  const handleSave = () => {
    setSaveToast(true);
    setTimeout(() => setSaveToast(false), 2500);
  };

  const handleAddTraveller = (e) => {
    e.preventDefault();
    if (!newTraveller.name || !newTraveller.age) return;
    setCoTravellers([
      ...coTravellers,
      {
        id: Date.now(),
        name: newTraveller.name,
        age: Number(newTraveller.age),
        gender: newTraveller.gender
      }
    ]);
    setNewTraveller({ name: '', age: '', gender: 'Male' });
    setShowAddModal(false);
  };

  const handleDeleteTraveller = (id) => {
    setCoTravellers(coTravellers.filter(t => t.id !== id));
  };

  return (
    <div className="min-h-screen bg-[#FAF9F6] font-poppins text-[#181E4B]">

      {/* ============================================================ */}
      {/* 1. TOP NATURE CANOPY BANNER (HOMEPAGE COLOR HARMONY)         */}
      {/* ============================================================ */}
      <div 
        className="w-full relative pt-24 pb-12 px-4 sm:px-8 text-white bg-cover bg-center"
        style={{
          backgroundImage: `linear-gradient(rgba(7, 36, 34, 0.85), rgba(7, 36, 34, 0.92)), url('/island.jpg')`,
          backgroundColor: '#072422'
        }}
      >
        <div className="max-w-6xl mx-auto">
          
          {/* Breadcrumb Row */}
          <div className="flex items-center gap-2 text-xs text-white/80 font-medium mb-6">
            <button 
              onClick={() => onNavigate('/')} 
              className="hover:text-white transition-colors cursor-pointer"
            >
              Home
            </button>
            <ChevronRight className="w-3.5 h-3.5 text-white/60" />
            <span className="text-white font-semibold">My Account</span>
          </div>

          {/* Profile Identity Bar */}
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
            
            {/* User Avatar Circle + Name & Contacts */}
            <div className="flex items-center gap-5">
              
              {/* Product-Matching Circle Avatar (Dark Pine & Emerald Ring - ZERO orange!) */}
              <div className="relative group">
                <div className="w-20 h-20 sm:w-22 sm:h-22 rounded-full bg-[#12423e] border-2 border-emerald-400/40 text-emerald-100 flex flex-col items-center justify-center shadow-lg transition-transform group-hover:scale-105 cursor-pointer">
                  <Camera className="w-6 h-6 text-emerald-300 mb-0.5" />
                  <span className="text-[10px] font-medium tracking-tight text-emerald-100">
                    Add Photo
                  </span>
                </div>
              </div>

              {/* Name & Contact Info */}
              <div>
                <h1 className="text-2xl sm:text-3xl font-bold font-volkhov text-white tracking-wide">
                  {formData.firstName} {formData.lastName}
                </h1>
                
                <div className="flex flex-wrap items-center gap-x-4 gap-y-1 mt-1.5 text-xs text-white/80">
                  <span className="flex items-center gap-1.5">
                    <Phone className="w-3.5 h-3.5 text-emerald-400" />
                    <span>{formData.phone || 'Add Mobile Number'}</span>
                  </span>
                  <span className="flex items-center gap-1.5">
                    <Mail className="w-3.5 h-3.5 text-emerald-400" />
                    <span>{formData.email}</span>
                  </span>
                </div>
              </div>

            </div>

            {/* Right Side Bookings Chip */}
            <div className="flex items-center gap-3">
              <button 
                onClick={() => onNavigate('/booking')}
                className="px-4 py-2 rounded-full bg-white/10 hover:bg-white/20 text-white text-xs font-medium border border-white/20 transition-colors flex items-center gap-1.5 cursor-pointer shadow-sm"
              >
                <span>My Bookings</span>
                <ChevronRight className="w-3.5 h-3.5 text-white/60" />
              </button>
            </div>

          </div>

        </div>
      </div>

      {/* ============================================================ */}
      {/* 2. MAIN 2-COLUMN WORKSPACE (HOMEPAGE MATCHING THEME)         */}
      {/* ============================================================ */}
      <div className="max-w-6xl mx-auto px-4 sm:px-8 py-8">
        <div className="grid grid-cols-1 md:grid-cols-12 gap-6 items-start">
          
          {/* ---------------------------------------------------------- */}
          {/* LEFT SIDEBAR: "MY ACCOUNT" MENU                            */}
          {/* ---------------------------------------------------------- */}
          <div className="md:col-span-4 lg:col-span-3 bg-white rounded-3xl border border-slate-200/80 shadow-sm p-4 space-y-1">
            
            <div className="px-3 py-2 text-[11px] font-bold text-[#5E6282] uppercase tracking-wider font-poppins">
              My Account
            </div>

            {/* Menu 1: My Profile */}
            <button
              onClick={() => setActiveMenu('profile')}
              className={`w-full flex items-center justify-between px-3.5 py-3 rounded-2xl text-xs font-semibold transition-colors cursor-pointer ${
                activeMenu === 'profile'
                  ? 'bg-[#072422] text-white shadow-sm'
                  : 'text-[#5E6282] hover:bg-slate-50 hover:text-[#181E4B]'
              }`}
            >
              <div className="flex items-center gap-2.5">
                <User className={`w-4 h-4 ${activeMenu === 'profile' ? 'text-emerald-300' : 'text-[#5E6282]'}`} />
                <span>My Profile</span>
              </div>
              <span className={`w-2 h-2 rounded-full ${activeMenu === 'profile' ? 'bg-[#DF6951]' : 'bg-[#DF6951]'}`} />
            </button>

            {/* Menu 2: Co-Travellers */}
            <button
              onClick={() => setActiveMenu('travelers')}
              className={`w-full flex items-center gap-2.5 px-3.5 py-3 rounded-2xl text-xs font-semibold transition-colors cursor-pointer ${
                activeMenu === 'travelers'
                  ? 'bg-[#072422] text-white shadow-sm'
                  : 'text-[#5E6282] hover:bg-slate-50 hover:text-[#181E4B]'
              }`}
            >
              <Users className={`w-4 h-4 ${activeMenu === 'travelers' ? 'text-emerald-300' : 'text-[#5E6282]'}`} />
              <span>Co-Travellers</span>
            </button>

            {/* Menu 3: Logout */}
            <button
              onClick={onLogout}
              className="w-full flex items-center gap-2.5 px-3.5 py-3 rounded-2xl text-xs font-semibold text-slate-500 hover:text-red-600 hover:bg-red-50/50 transition-colors cursor-pointer"
            >
              <LogOut className="w-4 h-4" />
              <span>Logout</span>
            </button>

            <div className="pt-3 border-t border-slate-100 my-2">
              <button
                onClick={() => setActiveMenu('reset-password')}
                className={`w-full flex items-center gap-2.5 px-3.5 py-2.5 rounded-2xl text-xs font-medium transition-colors cursor-pointer ${
                  activeMenu === 'reset-password'
                    ? 'text-[#072422] font-semibold bg-slate-50'
                    : 'text-[#5E6282] hover:text-[#181E4B]'
                }`}
              >
                <KeyRound className="w-4 h-4 text-slate-400" />
                <span>Reset Password</span>
              </button>
            </div>

          </div>

          {/* ---------------------------------------------------------- */}
          {/* RIGHT MAIN CONTENT: MY PROFILE FORM                        */}
          {/* ---------------------------------------------------------- */}
          <div className="md:col-span-8 lg:col-span-9 bg-white rounded-3xl border border-slate-200/80 shadow-sm p-6 sm:p-8 space-y-6">
            
            {/* VIEW 1: MY PROFILE FORM */}
            {activeMenu === 'profile' && (
              <>
                {/* Header Row: Title + Save Button */}
                <div className="flex items-center justify-between pb-4 border-b border-slate-100">
                  <h2 className="text-xl font-bold font-volkhov text-[#181E4B]">
                    My Profile
                  </h2>
                  <button
                    onClick={handleSave}
                    className="px-6 py-2 rounded-xl bg-[#DF6951] hover:bg-[#c95b44] text-white text-xs font-bold tracking-wider transition-colors cursor-pointer shadow-sm"
                  >
                    {saveToast ? 'SAVED ✓' : 'SAVE'}
                  </button>
                </div>

                {/* General Information Section */}
                <div className="space-y-4 pt-2">
                  <h3 className="text-sm font-bold text-[#181E4B] font-poppins">
                    General Information
                  </h3>

                  {/* Form Grid */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs font-poppins">
                    
                    {/* First & Middle Name */}
                    <div className="p-3.5 rounded-2xl bg-slate-50 border border-slate-200 focus-within:border-[#DF6951] focus-within:bg-white transition-colors">
                      <label className="block text-[10px] font-bold text-[#5E6282] uppercase tracking-wider mb-1">
                        First &amp; Middle Name
                      </label>
                      <input
                        type="text"
                        value={formData.firstName}
                        onChange={(e) => setFormData({ ...formData, firstName: e.target.value })}
                        className="w-full bg-transparent font-medium text-sm text-[#181E4B] focus:outline-none"
                      />
                    </div>

                    {/* Last Name */}
                    <div className="p-3.5 rounded-2xl bg-slate-50 border border-slate-200 focus-within:border-[#DF6951] focus-within:bg-white transition-colors">
                      <label className="block text-[10px] font-bold text-[#5E6282] uppercase tracking-wider mb-1">
                        Last Name
                      </label>
                      <input
                        type="text"
                        value={formData.lastName}
                        onChange={(e) => setFormData({ ...formData, lastName: e.target.value })}
                        className="w-full bg-transparent font-medium text-sm text-[#181E4B] focus:outline-none"
                      />
                    </div>

                    {/* Gender */}
                    <div className="p-3.5 rounded-2xl bg-slate-50 border border-slate-200 focus-within:border-[#DF6951] focus-within:bg-white transition-colors">
                      <label className="block text-[10px] font-bold text-[#5E6282] uppercase tracking-wider mb-1">
                        Gender
                      </label>
                      <select
                        value={formData.gender}
                        onChange={(e) => setFormData({ ...formData, gender: e.target.value })}
                        className="w-full bg-transparent font-medium text-sm text-[#181E4B] focus:outline-none cursor-pointer"
                      >
                        <option value="Male">Male</option>
                        <option value="Female">Female</option>
                        <option value="Other">Other</option>
                      </select>
                    </div>

                    {/* Age */}
                    <div className="p-3.5 rounded-2xl bg-slate-50 border border-slate-200 focus-within:border-[#DF6951] focus-within:bg-white transition-colors">
                      <label className="block text-[10px] font-bold text-[#5E6282] uppercase tracking-wider mb-1">
                        Age (Years)
                      </label>
                      <input
                        type="number"
                        min="1"
                        max="110"
                        value={formData.age}
                        onChange={(e) => setFormData({ ...formData, age: e.target.value })}
                        className="w-full bg-transparent font-medium text-sm text-[#181E4B] focus:outline-none font-mono"
                      />
                    </div>

                    {/* City of Residence */}
                    <div className="p-3.5 rounded-2xl bg-slate-50 border border-slate-200 focus-within:border-[#DF6951] focus-within:bg-white transition-colors">
                      <label className="block text-[10px] font-bold text-[#5E6282] uppercase tracking-wider mb-1">
                        City of Residence
                      </label>
                      <input
                        type="text"
                        value={formData.city}
                        onChange={(e) => setFormData({ ...formData, city: e.target.value })}
                        className="w-full bg-transparent font-medium text-sm text-[#181E4B] focus:outline-none"
                      />
                    </div>

                    {/* State */}
                    <div className="p-3.5 rounded-2xl bg-slate-50 border border-slate-200 focus-within:border-[#DF6951] focus-within:bg-white transition-colors">
                      <label className="block text-[10px] font-bold text-[#5E6282] uppercase tracking-wider mb-1">
                        State
                      </label>
                      <input
                        type="text"
                        value={formData.state}
                        onChange={(e) => setFormData({ ...formData, state: e.target.value })}
                        className="w-full bg-transparent font-medium text-sm text-[#181E4B] focus:outline-none"
                      />
                    </div>

                  </div>
                </div>

                {/* Contact Details Section */}
                <div className="space-y-3 pt-3 border-t border-slate-100">
                  <div>
                    <h3 className="text-sm font-bold text-[#181E4B] font-poppins">
                      Contact Details
                    </h3>
                    <p className="text-[11px] text-[#5E6282] mt-0.5">
                      Add contact information to receive booking details &amp; other alerts
                    </p>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs font-poppins pt-1">
                    
                    {/* Mobile Number Box */}
                    <div className="p-3.5 rounded-2xl bg-slate-50 border border-slate-200 focus-within:border-[#DF6951] focus-within:bg-white transition-colors">
                      <label className="block text-[10px] font-bold text-[#5E6282] uppercase tracking-wider mb-1">
                        Mobile Number
                      </label>
                      <input
                        type="text"
                        value={formData.phone}
                        onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                        className="w-full bg-transparent font-medium text-sm text-[#181E4B] focus:outline-none"
                        placeholder="Add Mobile Number"
                      />
                    </div>

                    {/* Email ID Box with Verified Checkmark */}
                    <div className="p-3.5 rounded-2xl bg-slate-50 border border-slate-200 focus-within:border-[#DF6951] focus-within:bg-white transition-colors flex items-center justify-between">
                      <div className="w-full">
                        <label className="block text-[10px] font-bold text-[#5E6282] uppercase tracking-wider mb-1">
                          Email ID
                        </label>
                        <input
                          type="email"
                          value={formData.email}
                          onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                          className="w-full bg-transparent font-medium text-sm text-[#181E4B] focus:outline-none"
                        />
                      </div>
                      <Check className="w-5 h-5 text-emerald-600 shrink-0 ml-2" />
                    </div>

                  </div>
                </div>
              </>
            )}

            {/* VIEW 2: CO-TRAVELLERS (JUST FULL NAME, AGE & GENDER) */}
            {activeMenu === 'travelers' && (
              <div className="space-y-5">
                <div className="flex items-center justify-between pb-4 border-b border-slate-100">
                  <div>
                    <h2 className="text-xl font-bold font-volkhov text-[#181E4B]">
                      Co-Travellers
                    </h2>
                    <p className="text-xs text-[#5E6282] mt-0.5">
                      Save details of co-travellers for fast 1-click booking
                    </p>
                  </div>
                  <button
                    onClick={() => setShowAddModal(true)}
                    className="px-4 py-2 rounded-xl bg-[#DF6951] hover:bg-[#c95b44] text-white text-xs font-semibold transition-colors flex items-center gap-1.5 cursor-pointer shadow-sm"
                  >
                    <Plus className="w-3.5 h-3.5" />
                    <span>Add Co-Traveller</span>
                  </button>
                </div>

                <div className="space-y-3">
                  {coTravellers.map((traveller, index) => (
                    <div
                      key={traveller.id}
                      className="p-4 rounded-2xl bg-slate-50 border border-slate-200/80 flex items-center justify-between"
                    >
                      <div className="flex items-center gap-3.5">
                        <div className="w-9 h-9 rounded-xl bg-[#072422] text-emerald-300 font-bold text-xs flex items-center justify-center shrink-0">
                          0{index + 1}
                        </div>
                        <div>
                          <div className="font-bold text-sm text-[#181E4B]">
                            {traveller.name}
                          </div>
                          <div className="text-xs text-[#5E6282] mt-0.5">
                            {traveller.gender} • Age: {traveller.age} years
                          </div>
                        </div>
                      </div>

                      <button
                        onClick={() => handleDeleteTraveller(traveller.id)}
                        className="text-slate-400 hover:text-red-500 p-1.5 transition-colors cursor-pointer"
                        title="Remove traveller"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* VIEW 3: RESET PASSWORD */}
            {activeMenu === 'reset-password' && (
              <div className="space-y-5 max-w-md">
                <div className="pb-4 border-b border-slate-100">
                  <h2 className="text-xl font-bold font-volkhov text-[#181E4B]">
                    Reset Password
                  </h2>
                  <p className="text-xs text-[#5E6282] mt-0.5">
                    Update your password to keep your travel bookings secure
                  </p>
                </div>

                <div className="space-y-3 text-xs font-poppins">
                  <div>
                    <label className="block text-[11px] font-semibold text-[#181E4B] mb-1">Current Password</label>
                    <input
                      type="password"
                      placeholder="Enter current password"
                      className="w-full px-3.5 py-2.5 rounded-xl border border-slate-300 focus:outline-none focus:border-[#DF6951] bg-slate-50"
                    />
                  </div>

                  <div>
                    <label className="block text-[11px] font-semibold text-[#181E4B] mb-1">New Password</label>
                    <input
                      type="password"
                      placeholder="Enter new password (min. 8 characters)"
                      className="w-full px-3.5 py-2.5 rounded-xl border border-slate-300 focus:outline-none focus:border-[#DF6951] bg-slate-50"
                    />
                  </div>

                  <div>
                    <label className="block text-[11px] font-semibold text-[#181E4B] mb-1">Confirm New Password</label>
                    <input
                      type="password"
                      placeholder="Confirm new password"
                      className="w-full px-3.5 py-2.5 rounded-xl border border-slate-300 focus:outline-none focus:border-[#DF6951] bg-slate-50"
                    />
                  </div>

                  <button
                    onClick={handleSave}
                    className="px-5 py-2.5 rounded-xl bg-[#072422] hover:bg-[#0f3d3a] text-white font-semibold text-xs transition-colors cursor-pointer mt-2"
                  >
                    Update Password
                  </button>
                </div>
              </div>
            )}

          </div>

        </div>
      </div>

      {/* ============================================================ */}
      {/* 3. MODAL: ADD CO-TRAVELLER (NAME, AGE & GENDER ONLY)         */}
      {/* ============================================================ */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm animate-fadeIn">
          <div className="bg-white rounded-3xl max-w-md w-full p-6 shadow-xl border border-slate-200 space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <h3 className="font-bold text-base text-[#181E4B] font-volkhov">
                Add Co-Traveller
              </h3>
              <button
                onClick={() => setShowAddModal(false)}
                className="w-7 h-7 rounded-full bg-slate-100 hover:bg-slate-200 text-slate-500 flex items-center justify-center text-xs cursor-pointer"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleAddTraveller} className="space-y-4 text-xs font-poppins">
              <div>
                <label className="block text-[11px] font-semibold text-[#181E4B] mb-1">Full Name *</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Ramesh Kumar"
                  value={newTraveller.name}
                  onChange={(e) => setNewTraveller({ ...newTraveller, name: e.target.value })}
                  className="w-full px-3.5 py-2.5 rounded-xl border border-slate-300 focus:outline-none focus:border-[#DF6951] bg-slate-50"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[11px] font-semibold text-[#181E4B] mb-1">Age *</label>
                  <input
                    type="number"
                    min="1"
                    max="115"
                    required
                    placeholder="e.g. 28"
                    value={newTraveller.age}
                    onChange={(e) => setNewTraveller({ ...newTraveller, age: e.target.value })}
                    className="w-full px-3.5 py-2.5 rounded-xl border border-slate-300 focus:outline-none focus:border-[#DF6951] bg-slate-50"
                  />
                </div>

                <div>
                  <label className="block text-[11px] font-semibold text-[#181E4B] mb-1">Gender</label>
                  <select
                    value={newTraveller.gender}
                    onChange={(e) => setNewTraveller({ ...newTraveller, gender: e.target.value })}
                    className="w-full px-3 py-2.5 rounded-xl border border-slate-300 focus:outline-none focus:border-[#DF6951] bg-slate-50"
                  >
                    <option value="Male">Male</option>
                    <option value="Female">Female</option>
                    <option value="Other">Other</option>
                  </select>
                </div>
              </div>

              <div className="pt-3 flex items-center justify-end gap-3 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className="px-4 py-2 rounded-xl text-slate-600 hover:bg-slate-100 font-medium cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-5 py-2 rounded-xl bg-[#DF6951] hover:bg-[#c95b44] text-white font-semibold cursor-pointer"
                >
                  Add Traveller
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

    </div>
  );
}
