import React, { useState, useEffect } from 'react';
import Navbar from './components/Navbar';
import PeeledSheetPull from './components/PeeledSheetPull';
import Hero from './components/Hero';
import ResilienceLogs from './components/ResilienceLogs';
import TravelDisputePlans from './components/TravelDisputePlans';
import TravelAgencySections from './components/TravelAgencySections';
import BookingPage from './booking/BookingPage';
import DisruptionPage from './disruption/DisruptionPage';
import ProfilePage from './profile/ProfilePage';
import AuthModal from './components/AuthModal';
import AgenticSagaModal from './components/AgenticSagaModal';
import Footer from './components/Footer';
import { translations } from './translations';

import {
  fetchItinerary,
  simulateDisruption,
  fetchRecoveryPlans,
  commitRecoveryPlan,
  fetchPassengerRights,
  resetItinerary
} from './api';

export default function App() {
  const [itinerary, setItinerary] = useState(null);
  const [riskAnalysis, setRiskAnalysis] = useState(null);
  const [activeDisruption, setActiveDisruption] = useState(null);
  const [activeImpact, setActiveImpact] = useState(null);
  const [recoveryPlans, setRecoveryPlans] = useState([]);
  const [passengerRights, setPassengerRights] = useState(null);
  const [isSimulating, setIsSimulating] = useState(false);
  
  // Real SPA Route state ('/' | '/booking' | '/profile')
  const [currentRoute, setCurrentRoute] = useState(
    typeof window !== 'undefined' ? (window.location.pathname || '/') : '/'
  );

  // Multi-Language state ('en' | 'mr' | 'hi')
  const [language, setLanguage] = useState('en');
  const t = translations[language] || translations.en;

  // User state
  const [user, setUser] = useState({ 
    name: 'Elena Vance', 
    email: 'elena.vance@voyage.io', 
    tier: 'Plus' 
  });

  // Auth Modal state
  const [isAuthOpen, setIsAuthOpen] = useState(false);
  const [authInitialTab, setAuthInitialTab] = useState('login');
  const [postAuthRedirect, setPostAuthRedirect] = useState(null);

  // Saga Modal state
  const [isSagaOpen, setIsSagaOpen] = useState(false);
  const [selectedPlanForSaga, setSelectedPlanForSaga] = useState(null);

  // Sync browser back/forward buttons
  useEffect(() => {
    const handlePopState = () => {
      setCurrentRoute(window.location.pathname || '/');
    };
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  // Initial load
  useEffect(() => {
    loadInitialData();
  }, []);

  const loadInitialData = async () => {
    try {
      const data = await fetchItinerary();
      if (data && data.itinerary) {
        setItinerary(data.itinerary);
        setRiskAnalysis(data.risk_analysis);
        if (data.itinerary.traveler_name && data.itinerary.traveler_name !== "Elena Vance (Corporate / Leisure)" && data.itinerary.traveler_name !== "Passenger") {
          setUser(prev => ({ ...prev, name: data.itinerary.traveler_name }));
        }
      } else {
        setItinerary({
          id: "itinerary_alpine_cascade",
          title: "The Alpine Expedition: London to Zermatt",
          traveler_name: "Elena Vance (Corporate / Leisure)",
          total_cost: 700.0,
          currency: "EUR",
          domino_risk_index: 48.2,
          nodes: [
            { id: "node_flight_1", name: "British Airways BA 712", type: "transport", mode: "flight", carrier: "British Airways", service_number: "BA 712", origin: "LHR", destination: "ZRH", start_time: "14:00", end_time: "16:45", duration_minutes: 165, cost: 240, status: "confirmed", slack_minutes: 45, mct_required: 45 },
            { id: "node_transfer_1", name: "Zurich Airport Transit Shuttle", type: "transport", mode: "walk", carrier: "Ground Link", service_number: "Air-Rail", origin: "ZRH T1", destination: "ZRH Rail", start_time: "17:15", end_time: "17:35", duration_minutes: 20, cost: 0, status: "confirmed", slack_minutes: 27, mct_required: 15 },
            { id: "node_train_1", name: "SBB InterCity IC 8", type: "transport", mode: "train", carrier: "SBB CFF FFS", service_number: "IC 8 #830", origin: "Zurich HB", destination: "Visp", start_time: "18:02", end_time: "20:02", duration_minutes: 120, cost: 98, status: "confirmed", slack_minutes: 8, mct_required: 10 },
            { id: "node_train_2", name: "Matterhorn Gotthard Bahn Regional", type: "transport", mode: "train", carrier: "MGB", service_number: "Reg 138", origin: "Visp", destination: "Zermatt", start_time: "20:10", end_time: "21:14", duration_minutes: 64, cost: 42, status: "confirmed", slack_minutes: 16, mct_required: 8 },
            { id: "node_hotel_1", name: "Boutique Hotel Matterhorn Lodge", type: "reservation", carrier: "Matterhorn Hospitality", service_number: "RES-88219", origin: "Zermatt", destination: "Zermatt", start_time: "20:30", end_time: "23:59", duration_minutes: 209, cost: 320, status: "confirmed", slack_minutes: 30, checkin_cutoff: "21:00", critical_anchor: true }
          ],
          edges: [
            { source_id: "node_flight_1", target_id: "node_transfer_1", slack: 30, min_connection_time: 30 },
            { source_id: "node_transfer_1", target_id: "node_train_1", slack: 27, min_connection_time: 20 },
            { source_id: "node_train_1", target_id: "node_train_2", slack: 8, min_connection_time: 8 },
            { source_id: "node_train_2", target_id: "node_hotel_1", slack: 16, min_connection_time: 15 }
          ]
        });
        setRiskAnalysis({
          domino_risk_index: 48.2,
          level: "MODERATE",
          color: "#F59E0B",
          advice: "Tight connections detected at Zurich and Visp. Hotel check-in closes at 21:00 strict."
        });
      }

      const plansData = await fetchRecoveryPlans();
      if (plansData && plansData.plans) {
        setRecoveryPlans(plansData.plans);
      }

      const rightsData = await fetchPassengerRights();
      if (rightsData) {
        setPassengerRights(rightsData);
      }
    } catch (e) {
      console.warn("Error loading initial data:", e);
    }
  };

  const handleSimulateDisruption = async (disruptionPayload) => {
    setIsSimulating(true);
    try {
      const data = await simulateDisruption(disruptionPayload || {
        node_id: "node_flight_1",
        delay_minutes: 65,
        is_cancellation: false,
        reason: "Air Traffic Control Ground Delay Program at LHR (+65m)"
      });
      if (data) {
        setActiveDisruption(data.disruption);
        setActiveImpact(data.impact);
        setRiskAnalysis(data.risk_analysis);
        if (data.recovery_plans) {
          setRecoveryPlans(data.recovery_plans);
        }
      }
    } catch (e) {
      console.error("Simulation error:", e);
    } finally {
      setIsSimulating(false);
    }
  };

  const handleNavigate = (path) => {
    setCurrentRoute(path);
    if (typeof window !== 'undefined') {
      window.history.pushState(null, '', path);
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }
  };

  const handleOpenAuth = (tab = 'login', redirectAfter = null) => {
    setAuthInitialTab(tab);
    setPostAuthRedirect(redirectAfter);
    setIsAuthOpen(true);
  };

  const handleLoginSuccess = (userData) => {
    setUser(userData);
    setIsAuthOpen(false);
    if (postAuthRedirect) {
      handleNavigate(postAuthRedirect);
      setPostAuthRedirect(null);
    }
  };

  const handleResetItinerary = async () => {
    try {
      await resetItinerary();
    } catch (e) {
      console.error(e);
    }
    setActiveDisruption(null);
    setActiveImpact(null);
    loadInitialData();
  };

  const handleOpenSagaModal = (plan) => {
    setSelectedPlanForSaga(plan || recoveryPlans[0]);
    setIsSagaOpen(true);
  };

  const handleCommitSuccess = (committedPlan) => {
    setIsSagaOpen(false);
    setActiveDisruption(null);
    loadInitialData();
  };

  return (
    <div className="min-h-screen relative flex flex-col bg-[#FAF9F6] text-voyare-navy font-poppins selection:bg-voyare-coral selection:text-white">
      
      {/* 1. SINGLE-LINE UNIFIED NAVBAR (All in the same line without stickers) */}
      <Navbar
        activeDisruption={activeDisruption}
        onOpenSaga={() => handleOpenSagaModal(recoveryPlans[0])}
        onQuickSimulate={() => handleSimulateDisruption({
          node_id: "node_flight_1",
          delay_minutes: 65,
          is_cancellation: false,
          reason: "Air Traffic Control Ground Delay Program at LHR (+65m)"
        })}
        user={user}
        onLogout={() => { setUser(null); handleNavigate('/'); }}
        onOpenAuth={handleOpenAuth}
        onNavigate={handleNavigate}
        currentRoute={currentRoute}
        language={language}
        onSelectLanguage={setLanguage}
        t={t}
      />

      {/* 2. DEDICATED ROUTE: /booking */}
      {currentRoute === '/booking' && (
        <BookingPage
          user={user}
          itinerary={itinerary}
          activeDisruption={activeDisruption}
          onNavigate={handleNavigate}
          onSimulateAlpine={() => handleSimulateDisruption()}
          t={t}
        />
      )}

      {/* 3. DEDICATED ROUTE: /profile */}
      {currentRoute === '/profile' && (
        <ProfilePage
          user={user}
          onNavigate={handleNavigate}
          onLogout={() => { setUser(null); handleNavigate('/'); }}
          t={t}
        />
      )}

      {/* 4. DEDICATED ROUTE: /disruption (Disruption Resolver) */}
      {currentRoute === '/disruption' && (
        <DisruptionPage
          user={user}
          itinerary={itinerary}
          activeDisruption={activeDisruption}
          onNavigate={handleNavigate}
          onSimulateAlpine={handleSimulateDisruption}
          onResetDisruption={handleResetItinerary}
          onOpenSaga={handleOpenSagaModal}
          t={t}
        />
      )}

      {/* 5. MAIN ROUTE: / (Landing Page with 3D Peeled Sheet & Full Platform) */}
      {currentRoute !== '/booking' && currentRoute !== '/profile' && currentRoute !== '/disruption' && (
        <PeeledSheetPull
          activeDisruption={activeDisruption}
          onSimulateAlpine={() => handleSimulateDisruption({
            node_id: "node_flight_1",
            delay_minutes: 65,
            is_cancellation: false,
            reason: "Air Traffic Control Ground Delay Program at LHR (+65m)"
          })}
          t={t}
        >
          {/* Section 1: Hero with Demo Journey in Format of Map (Replaced div[1]) */}
          <Hero
            itinerary={itinerary}
            activeDisruption={activeDisruption}
            onSimulateAlpine={() => handleSimulateDisruption({
              node_id: "node_flight_1",
              delay_minutes: 65,
              is_cancellation: false,
              reason: "Air Traffic Control Ground Delay Program at LHR (+65m)"
            })}
            onOpenSaga={() => handleOpenSagaModal(recoveryPlans[0])}
            t={t}
          />

          {/* Section 2: Minimal Logs Format (Low-latency Telemetry Stream) */}
          <ResilienceLogs
            itinerary={itinerary}
            activeDisruption={activeDisruption}
            t={t}
          />

          {/* Section 3: Travel Dispute & Disruption Plans in ALL-WHITE Format */}
          <TravelDisputePlans
            user={user}
            onOpenAuth={handleOpenAuth}
            onNavigate={handleNavigate}
            onSelectPlan={(planKey) => handleOpenSagaModal(recoveryPlans[0])}
            activeDisruption={activeDisruption}
            t={t}
          />

          {/* Section 4: Travel Agency Sections from Figma (Services, Destinations, Testimonials) */}
          <TravelAgencySections
            onSimulateAlpine={() => handleSimulateDisruption({
              node_id: "node_flight_1",
              delay_minutes: 65,
              is_cancellation: false,
              reason: "Air Traffic Control Ground Delay Program at LHR (+65m)"
            })}
            onOpenSaga={() => handleOpenSagaModal(recoveryPlans[0])}
            activeDisruption={activeDisruption}
            t={t}
          />

          {/* Section 5: Footer */}
          <Footer />
        </PeeledSheetPull>
      )}

      {/* Auth Modal (Login / Sign Up) */}
      <AuthModal
        isOpen={isAuthOpen}
        onClose={() => setIsAuthOpen(false)}
        onLoginSuccess={handleLoginSuccess}
        initialTab={authInitialTab}
        t={t}
      />

      {/* Distributed Saga Orchestrator Modal */}
      <AgenticSagaModal
        plan={selectedPlanForSaga}
        isOpen={isSagaOpen}
        onClose={() => setIsSagaOpen(false)}
        onCommitSuccess={handleCommitSuccess}
      />

    </div>
  );
}
