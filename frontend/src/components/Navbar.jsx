import React, { useState } from 'react';
import { Menu, X, ChevronDown, Compass, LogOut, Check } from 'lucide-react';

export default function Navbar({ 
  activeDisruption, 
  onOpenSaga, 
  onQuickSimulate,
  user,
  onLogout,
  onOpenAuth,
  onNavigate,
  currentRoute = '/',
  language,
  onSelectLanguage,
  t
}) {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [langDropdownOpen, setLangDropdownOpen] = useState(false);

  const scrollTo = (id) => {
    setMobileMenuOpen(false);
    if (currentRoute !== '/') {
      onNavigate('/');
      setTimeout(() => {
        const el = document.querySelector(id);
        if (el) el.scrollIntoView({ behavior: 'smooth' });
      }, 100);
      return;
    }
    if (id === '#hero') {
      window.scrollTo({ top: 0, behavior: 'smooth' });
      return;
    }
    const el = document.querySelector(id);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth' });
    }
  };

  const handleBookNow = () => {
    setMobileMenuOpen(false);
    onNavigate('/booking');
  };

  const handleProfileClick = () => {
    setMobileMenuOpen(false);
    if (!user) {
      onOpenAuth('login', '/profile');
    } else {
      onNavigate('/profile');
    }
  };

  const handleDisruptionSolving = () => {
    setMobileMenuOpen(false);
    onNavigate('/disruption');
  };

  const languages = [
    { code: 'en', label: 'English (EN)' },
    { code: 'mr', label: 'मराठी (MR)' },
    { code: 'hi', label: 'हिन्दी (HI)' }
  ];

  return (
    <>
      {/* ========================================================================= */}
      {/* UNIFIED SINGLE-LINE NAVBAR (Everything in the SAME LINE as requested)     */}
      {/* No multi-row stacking, pure clean vector logo without stickers!           */}
      {/* ========================================================================= */}
      <header className="fixed top-3 sm:top-4 left-0 right-0 z-[100] flex justify-center px-3 sm:px-6 pointer-events-none">
        <nav className="pointer-events-auto w-full max-w-4xl rounded-full px-3.5 sm:px-5 py-1.5 sm:py-2 flex items-center justify-between bg-[#072422]/90 backdrop-blur-xl border border-white/20 shadow-[0_8px_32px_rgba(0,0,0,0.4)] transition-all duration-300">
          
          {/* LEFT: EXACT UPLOADED VOYAGE LOGO */}
          <div className="flex items-center shrink-0 pr-3 sm:pr-4">
            <button
              onClick={() => onNavigate('/')}
              className="flex items-center hover:opacity-90 transition-opacity cursor-pointer"
              aria-label="Voyage Home"
            >
              <img 
                src="/voyage_logo.png" 
                alt="VOYAGE" 
                className="h-5 sm:h-6 w-auto object-contain"
              />
            </button>
          </div>

          {/* CENTER: NAV LINKS */}
          <div className="hidden md:flex items-center gap-6 lg:gap-8">
            <button
              onClick={() => scrollTo('#destinations')}
              className="font-googleSans font-normal text-xs lg:text-sm text-white/85 hover:text-white transition-colors duration-200 whitespace-nowrap cursor-pointer hover:drop-shadow-[0_0_8px_rgba(255,255,255,0.4)]"
            >
              {t?.destinations || 'Destinations'}
            </button>
          </div>

          {/* RIGHT: ALL CONTROLS IN THE SAME LINE (Buttons, Language, Profile/Auth) */}
          <div className="flex items-center gap-2 sm:gap-3 shrink-0">
            
            {/* Book Now (clean dark outlined pill) */}
            <button
              onClick={handleBookNow}
              className="hidden sm:inline-flex px-3 py-1 rounded-full border border-white/35 bg-white/10 hover:bg-white/20 text-white font-medium text-xs active:scale-95 transition-all whitespace-nowrap cursor-pointer"
            >
              {t?.bookNow || 'Book Now'}
            </button>

            {/* Resolve Disruption (terracotta filled pill #A35645) */}
            <button
              onClick={handleDisruptionSolving}
              className="px-3 py-1 rounded-full font-bold text-xs text-white bg-[#A35645] hover:bg-[#b8614e] transition-all shadow-md active:scale-95 whitespace-nowrap cursor-pointer"
            >
              {t?.resolveDisruption || 'Resolve Disruption'}
            </button>

            {/* Vertical Divider */}
            <div className="w-px h-3.5 bg-white/25 hidden sm:block" />

            {/* Language Switcher Dropdown (EN, Marathi, Hindi) */}
            <div className="relative">
              <button
                onClick={() => setLangDropdownOpen(!langDropdownOpen)}
                className="flex items-center gap-1 font-googleSans font-medium text-xs text-white/90 hover:text-white cursor-pointer px-1 py-0.5"
                aria-label="Select Language"
              >
                <span>{language?.toUpperCase() || 'EN'}</span>
                <ChevronDown className="w-3 h-3 text-white/70" />
              </button>

              {langDropdownOpen && (
                <div className="absolute top-8 right-0 w-36 bg-[#0c2328] border border-white/20 rounded-xl shadow-2xl overflow-hidden py-1 z-50 animate-fadeIn">
                  {languages.map((l) => (
                    <button
                      key={l.code}
                      onClick={() => {
                        onSelectLanguage(l.code);
                        setLangDropdownOpen(false);
                      }}
                      className={`w-full px-3.5 py-2 text-left text-xs font-poppins flex items-center justify-between transition-colors ${
                        language === l.code ? 'bg-white/15 text-white font-bold' : 'text-white/80 hover:bg-white/10 hover:text-white'
                      }`}
                    >
                      <span>{l.label}</span>
                      {language === l.code && <Check className="w-3 h-3 text-[#F1A501]" />}
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* User Profile Picture (Redirects to /profile) OR Login & Sign Up */}
            {user ? (
              <div className="flex items-center gap-1.5 pl-0.5">
                {/* Clicking profile avatar redirects to /profile */}
                <button
                  onClick={handleProfileClick}
                  title="View Profile (http://127.0.0.1:8000/profile)"
                  className="flex items-center gap-1.5 group cursor-pointer focus:outline-none"
                >
                  <div className="w-6.5 h-6.5 sm:w-7 sm:h-7 rounded-full bg-gradient-to-tr from-[#F1A501] to-[#DF6951] text-white flex items-center justify-center font-bold text-xs ring-2 ring-white/30 group-hover:ring-white transition-all shadow-md">
                    {user.name.charAt(0)}
                  </div>
                  <span className="hidden xl:inline text-xs text-white/90 group-hover:text-white font-medium">
                    {user.name.split(' ')[0]}
                  </span>
                </button>

                <button
                  onClick={onLogout}
                  title={t?.logout || "Logout"}
                  className="text-white/50 hover:text-white cursor-pointer p-1"
                >
                  <LogOut className="w-3.5 h-3.5" />
                </button>
              </div>
            ) : (
              <div className="flex items-center gap-2 pl-1">
                <button
                  onClick={() => onOpenAuth('login')}
                  className="font-googleSans font-medium text-xs text-white/90 hover:text-white transition-colors cursor-pointer whitespace-nowrap"
                >
                  {t?.login || 'Login'}
                </button>
                <button
                  onClick={() => onOpenAuth('signup')}
                  className="font-googleSans font-medium text-xs text-white px-2.5 py-1 rounded-[6px] border border-white/60 hover:border-white hover:bg-white/10 transition-all cursor-pointer whitespace-nowrap hidden sm:inline-block"
                >
                  {t?.signup || 'Sign up'}
                </button>
              </div>
            )}

            {/* Mobile Menu Toggle Button */}
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="md:hidden text-white/90 hover:text-white p-1 rounded-full hover:bg-white/10 transition-colors ml-1"
              aria-label="Toggle menu"
            >
              {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </button>

          </div>

        </nav>
      </header>

      {/* Mobile Drawer */}
      {mobileMenuOpen && (
        <div className="fixed inset-0 z-40 bg-[#072422]/98 backdrop-blur-2xl flex flex-col items-center justify-center p-6 space-y-5 md:hidden">
          <div className="w-full flex justify-between items-center pb-4 border-b border-white/10">
            <img 
              src="/voyage_logo.png" 
              alt="VOYAGE" 
              className="h-6 w-auto object-contain"
            />
            <button onClick={() => setMobileMenuOpen(false)} className="text-white p-2">
              <X className="w-6 h-6" />
            </button>
          </div>

          <div className="flex flex-col items-center gap-4 w-full">
            <button
              onClick={() => scrollTo('#destinations')}
              className="text-base font-googleSans text-white/90 hover:text-white font-medium py-1"
            >
              {t?.destinations || 'Destinations'}
            </button>
            {user && (
              <button
                onClick={handleProfileClick}
                className="text-base font-googleSans text-amber-400 font-medium py-1"
              >
                Profile ({user.name})
              </button>
            )}
          </div>

          <div className="w-full pt-4 border-t border-white/10 flex flex-col gap-2.5">
            <button
              onClick={handleBookNow}
              className="w-full py-2.5 rounded-xl border border-white/35 text-white font-medium text-xs"
            >
              {t?.bookNow || 'Book Now'}
            </button>
            <button
              onClick={handleDisruptionSolving}
              className="w-full py-2.5 rounded-xl bg-[#A35645] text-white font-bold text-xs"
            >
              {t?.resolveDisruption || 'Resolve Disruption'}
            </button>
          </div>
        </div>
      )}
    </>
  );
}
