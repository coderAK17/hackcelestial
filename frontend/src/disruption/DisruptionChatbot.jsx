import React, { useState, useRef, useEffect } from 'react';
import { 
  Send, Mic, MicOff, Paperclip, Sparkles, CheckCircle2, 
  AlertTriangle, ArrowRight, X, Minimize2, Maximize2, 
  FileText, ShieldCheck, Clock, RefreshCw, Volume2, Copy, Check,
  Settings, Key, Bot, Code, HelpCircle, Trash2, UploadCloud,
  MessageSquare, Map, ExternalLink, Compass, Layers, Train, Plane,
  Bus, Sun, Moon, Sunrise, Sunset, Calendar
} from 'lucide-react';

export default function DisruptionChatbot({
  isOpen,
  isMinimized,
  isFloating = false,
  onMinimize,
  onRestore,
  onEndChat,
  onTicketProcessed,
  onProceedToMap,
  onCheckRefundPolicy,
  t
}) {
  const [messages, setMessages] = useState([
    {
      id: 1,
      sender: 'bot',
      provider: 'Voyage AI Engine',
      text: "Hello! I am your Voyage AI Travel Assistant.\n\nI can analyze travel delays, assess downstream connections, evaluate passenger rights, parse tickets, and assist with your journey.\n\nHow can I help you today?",
      timestamp: "Just now"
    }
  ]);
  const [inputText, setInputText] = useState('');
  const [isRecording, setIsRecording] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [activeProvider, setActiveProvider] = useState('Voyage AI Engine');
  const [showSettings, setShowSettings] = useState(false);
  const [groqKey, setGroqKey] = useState(localStorage.getItem('voyage_groq_key') || '');
  const [geminiKey, setGeminiKey] = useState(localStorage.getItem('voyage_gemini_key') || '');
  const [currentDisruption, setCurrentDisruption] = useState(null);
  const [uploadedTickets, setUploadedTickets] = useState([]);
  const [isDragging, setIsDragging] = useState(false);
  const [copiedId, setCopiedId] = useState(null);

  const messagesEndRef = useRef(null);
  const chatContainerRef = useRef(null);
  const fileInputRef = useRef(null);
  const textInputRef = useRef(null);
  const recognitionRef = useRef(null);

  // Helper to reliably detect past dates across varied date formats
  const isPastDate = (dateStr) => {
    if (!dateStr) return false;
    const clean = String(dateStr).trim();
    if (/yesterday|completed|past/i.test(clean)) return true;
    const parsed = Date.parse(clean);
    if (!isNaN(parsed)) {
      const d = new Date(parsed);
      const today = new Date();
      today.setHours(0, 0, 0, 0);
      if (d < today) return true;
    }
    const parts = clean.split(/[-/.\s]+/);
    if (parts.length >= 3) {
      let day = parseInt(parts[0], 10);
      let month = parseInt(parts[1], 10) - 1;
      let year = parseInt(parts[2], 10);
      const monthNames = {
        jan: 0, feb: 1, mar: 2, apr: 3, may: 4, jun: 5,
        jul: 6, aug: 7, sep: 8, oct: 9, nov: 10, dec: 11
      };
      const mStr = parts[1].toLowerCase().slice(0, 3);
      if (monthNames[mStr] !== undefined) month = monthNames[mStr];
      if (parts[0].length === 4) {
        year = parseInt(parts[0], 10);
        month = parseInt(parts[1], 10) - 1;
        day = parseInt(parts[2], 10);
      }
      if (year < 100) year += 2000;
      if (year < new Date().getFullYear()) return true;
      const d = new Date(year, month, day);
      if (!isNaN(d.getTime())) {
        const today = new Date();
        today.setHours(0, 0, 0, 0);
        return d < today;
      }
    }
    return false;
  };

  const isPastTicket = (ticket) => {
    if (!ticket) return false;
    return Boolean(ticket.is_past_journey) || 
           ticket.journey_status === 'COMPLETED' || 
           isPastDate(ticket.travel_date);
  };

  // Load authentic tickets and disruptions from SQLite database on mount
  useEffect(() => {
    const loadRealTickets = async () => {
      try {
        const res = await fetch('/api/disruptions/external');
        if (res.ok) {
          const data = await res.json();
          if (data.disruptions && data.disruptions.length > 0) {
            const valid = data.disruptions.filter(d => 
              d.origin !== 'Origin' && 
              !(d.carrier === 'IndiGo' && (d.service_number === '6E 412' || d.service_number === '6E 441'))
            );
            if (valid.length > 0) {
              const latest = valid[0];
              setUploadedTickets([latest]);
              setCurrentDisruption(latest);
            }
          }
        }
      } catch (err) {
        console.warn("Could not load real tickets from database:", err);
      }
    };
    loadRealTickets();
  }, []);

  // Auto-scroll inside chat container strictly without scrolling the browser window
  useEffect(() => {
    if (chatContainerRef.current) {
      chatContainerRef.current.scrollTop = chatContainerRef.current.scrollHeight;
    }
  }, [messages, isRecording, isLoading]);

  // Clear chat conversation
  const handleClearChat = () => {
    setMessages([
      {
        id: 1,
        sender: 'bot',
        provider: 'Voyage AI Engine',
        text: "Conversation cleared. How may I assist your travel today? You can drag & drop tickets, type, or speak.",
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      }
    ]);
    setCurrentDisruption(null);
    setUploadedTickets([]);
  };

  // Toggle voice recognition
  const toggleVoiceRecording = () => {
    if (isRecording) {
      if (recognitionRef.current) {
        recognitionRef.current.stop();
      }
      setIsRecording(false);
      return;
    }

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      alert("Speech recognition is not supported in this browser. Please use Chrome, Edge, or Safari.");
      return;
    }

    try {
      const recognition = new SpeechRecognition();
      recognition.lang = 'en-US';
      recognition.interimResults = false;
      recognition.maxAlternatives = 1;

      recognition.onstart = () => {
        setIsRecording(true);
      };

      recognition.onresult = (event) => {
        const transcript = event.results[0][0].transcript;
        setInputText(prev => prev ? `${prev} ${transcript}` : transcript);
      };

      recognition.onerror = (event) => {
        console.warn("Speech recognition error:", event.error);
        setIsRecording(false);
      };

      recognition.onend = () => {
        setIsRecording(false);
      };

      recognitionRef.current = recognition;
      recognition.start();
    } catch (e) {
      console.error("Speech recognition startup error:", e);
      setIsRecording(false);
    }
  };

  // Save custom API keys
  const handleSaveKeys = (e) => {
    e.preventDefault();
    localStorage.setItem('voyage_groq_key', groqKey);
    localStorage.setItem('voyage_gemini_key', geminiKey);
    setShowSettings(false);
    setMessages(prev => [
      ...prev,
      {
        id: Date.now(),
        sender: 'bot',
        provider: 'System Configuration',
        text: "Custom API keys updated. Automatic failover: Groq (Llama 3.3 70B) ➔ Google Gemini (Gemini 2.0 Flash) ➔ Local Resilience Engine.",
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      }
    ]);
  };

  // Client-side domain restriction & travel resilience fallback handler
  const evaluateClientSideDomainResponse = (queryText, activeTicket, ticketsList) => {
    const q = (queryText || '').toLowerCase().trim();

    // 1. Off-topic domain check: block code writing, math problem solving, general non-travel tasks
    const codePhrases = [
      "write code", "generate code", "code for", "write a program", "write a script",
      "python code", "java code", "c++ code", "javascript code", "typescript code",
      "html code", "css code", "react code", "sql query", "write a function", "write a class",
      "binary search", "bubble sort", "quick sort", "linked list", "fibonacci", "factorial",
      "snake game", "tic tac toe", "tictactoe", "calculator app", "web scraper", "bot script",
      "python script", "bash script", "create a website", "build a website", "develop an app",
      "write an algorithm", "solve leetcode", "code in python", "code in java"
    ];
    const isCode = codePhrases.some(cp => q.includes(cp)) || 
      (["python", "java", "javascript", "typescript", "c++", "react", "html", "css", "algorithm"].some(lang => q.includes(lang)) && 
       ["write", "code", "create", "build", "develop", "implement", "generate", "script"].some(act => q.includes(act)) &&
       !["travel", "flight", "train", "pnr", "irctc", "dgca", "disruption", "refund", "voyage"].some(tk => q.includes(tk)));

    if (isCode) {
      return {
        text: `### 🛡️ Voyage AI Domain Guard\n\nI am **Voyage AI**, an autonomous AI concierge dedicated exclusively to **travel disruption resilience, flight & train telemetry, and statutory passenger rights** under DGCA CAR Section 3, EU261, US DOT, and IRCTC.\n\nI have a **domain restriction** and cannot generate software code, scripts, algorithms, or programming tutorials for non-travel applications.\n\n#### ✈️ How I can assist you with travel:\n- **Flight & Train Delay Analytics**: Track live operational status and downstream connection risk.\n- **Statutory Passenger Rights**: Calculate cash refunds, compensation, and meal entitlements.\n- **Multi-Modal Recovery Plans**: Recommend alternative air, rail, metro, or road connections.\n\n*Please let me know if you would like help with an upcoming flight, train, or travel disruption!*`,
        provider: "Voyage Domain Guard"
      };
    }

    const mathPhrases = [
      "solve equation", "solve math", "solve calculus", "math problem", "math question",
      "derivative of", "integral of", "calculate equation", "algebra problem",
      "trigonometry", "pythagorean", "quadratic formula", "solve 2x", "solve 3x", "solve 4x", "solve 5x", "solve x",
      "evaluate expression", "solve expression", "math homework"
    ];
    const isMath = mathPhrases.some(mp => q.includes(mp)) ||
      (/^(\s*what\s+is\s*)?\d+\s*[\+\-\*\/]\s*\d+\s*\??$/i.test(q) && !["refund", "fare", "delay", "ticket", "cost", "compensation", "pnr"].some(tk => q.includes(tk)));

    if (isMath) {
      return {
        text: `### 🛡️ Voyage AI Domain Guard\n\nI am **Voyage AI**, an autonomous AI concierge dedicated exclusively to **travel disruption resilience, flight & train telemetry, and statutory passenger rights**.\n\nI cannot solve general math homework, algebra, calculus, or scientific equations unrelated to travel.\n\n#### ✈️ How I can assist you with travel calculations:\n- **Statutory Compensation**: Calculate mandatory DGCA CAR Section 3 & EU261 cash payouts based on delay hours.\n- **IRCTC TDR Refund Calculation**: Compute 100% full fare refund eligibility for delayed train journeys.\n- **Connection Slack Computation**: Evaluate Critical Path Method (CPM) connection windows.\n\n*Please share your flight or train details to calculate disruption compensation or fare refunds!*`,
        provider: "Voyage Domain Guard"
      };
    }

    const offTopicTasks = [
      "write an essay", "write a story", "write a poem", "tell me a joke",
      "recipe for", "how to cook", "who won the", "capital of france",
      "who is president", "movie review", "summarize book", "tell me about yourself"
    ];
    if (offTopicTasks.some(ott => q.includes(ott))) {
      return {
        text: `### 🛡️ Voyage AI Domain Guard\n\nI am **Voyage AI**, an autonomous AI concierge dedicated exclusively to **travel disruption resilience, flight & train telemetry, and statutory passenger rights**.\n\nI cannot assist with general off-topic tasks (such as general essays, trivia, jokes, or non-travel queries).\n\n#### ✈️ How I can assist you:\n- **Flight & Train Telemetry**: Search schedules, check live status, and monitor delay risk.\n- **Passenger Rights & Refunds**: File statutory refund claims under DGCA, IRCTC, EU261, or US DOT.\n- **Multi-Modal Route Optimization**: Plan backup connections across air, rail, and road.\n\n*Please let me know how I can help with your travel itinerary!*`,
        provider: "Voyage Domain Guard"
      };
    }

    // 2. Travel Query Fallback (Itinerary / Refund Claims / Flight & Train Status)
    if (q.includes("claim") || q.includes("refund") || q.includes("dispute")) {
      return {
        text: `### 🛡️ Statutory Passenger Rights & Dispute Ledger\n\nUnder **DGCA CAR Section 3 (Air)** and **IRCTC TDR Regulations (Rail)**:\n\n• **Train Delays > 3 Hours**: 100% full statutory refund with zero cancellation deductions.\n• **Flight Delays > 6 Hours / Cancellations**: Full refund + ₹5,000 to ₹10,000 statutory compensation.\n• **Duty of Care**: Free meals and refreshments for delays exceeding 2 hours at departure.\n\n*You can click "File Refund Claim" on your ticket card to record a digital dispute claim.*`,
        provider: "Voyage Passenger Rights Engine"
      };
    }

    if (activeTicket) {
      const carrier = activeTicket.carrier || "Transit Operator";
      const service = activeTicket.service_number || "Service";
      const orig = activeTicket.origin || "Origin";
      const dest = activeTicket.destination || "Destination";
      const pnr = activeTicket.pnr || "VY-RECORD";
      const delayM = parseInt(activeTicket.delay_minutes || 0, 10);
      const delayTxt = delayM > 0 ? `+${delayM} mins delay` : "Running Right Time (On Schedule)";

      return {
        text: `### ✈️ Trip Status & Telemetry :: ${carrier} ${service}\n\n• **Route**: **${orig} ➔ ${dest}** (PNR: \`${pnr}\`)\n• **Operating Status**: **${delayTxt}**\n• **Passenger Rights**: ${delayM >= 180 ? 'Eligible for 100% statutory refund and statutory compensation.' : 'Operating nominally under standard schedule.'}\n\n*Click "Done (View Map)" to inspect the topological connection map or explore alternative Vande Bharat / Express links.*`,
        provider: "Voyage Travel Telemetry Engine"
      };
    }

    return {
      text: `### ✈️ Voyage Travel Intelligence Engine\n\nI am monitoring live multi-modal travel corridors across air, rail, and road transit.\n\n- **Flight & Train Search**: Enter a route (e.g. *"search flights from Mumbai to Delhi"* or train number *"12137"*).\n- **Disruption Analysis**: Upload a ticket PDF/image to calculate delay risk and statutory refund rights.\n\n*How would you like to plan your journey today?*`,
      provider: "Voyage Intelligence Engine"
    };
  };

  // Send message to AI engine
  const handleSendMessage = async (textToSend) => {
    const query = textToSend || inputText.trim();
    if (!query) return;

    const userMsg = {
      id: Date.now(),
      sender: 'user',
      text: query,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };

    const updatedMessages = [...messages, userMsg];
    setMessages(updatedMessages);
    setInputText('');
    setIsLoading(true);

    const activeTicketContext = currentDisruption || (uploadedTickets.length > 0 ? uploadedTickets[0] : null);

    try {
      const formattedHistory = updatedMessages.map(m => ({
        role: m.sender === 'user' ? 'user' : 'assistant',
        content: m.text
      }));

      const res = await fetch('/api/ai/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          messages: formattedHistory,
          query: query,
          groq_key: groqKey || undefined,
          gemini_key: geminiKey || undefined,
          active_ticket: activeTicketContext,
          uploaded_tickets: uploadedTickets.length > 0 ? uploadedTickets : undefined
        })
      });

      const contentType = res.headers.get("content-type") || "";
      if (!res.ok || !contentType.includes("application/json")) {
        throw new Error(`Non-JSON API response (${res.status})`);
      }

      const data = await res.json();
      const replyText = data.reply || "I have received your request and evaluated the disruption.";
      const provider = data.provider || "Voyage AI Engine";
      setActiveProvider(provider);

      if (data.all_tickets && Array.isArray(data.all_tickets) && data.all_tickets.length > 0) {
        setUploadedTickets(data.all_tickets);
      }

      const lower = query.toLowerCase();
      let cardToShow = null;
      if (data.structured_ticket) {
        cardToShow = data.structured_ticket;
        setCurrentDisruption(cardToShow);
        if (onTicketProcessed) onTicketProcessed(cardToShow);
      } else if (activeTicketContext && (
        lower.includes("my trip") || 
        lower.includes("my ticket") || 
        lower.includes("my train") || 
        lower.includes("my flight") || 
        lower.includes("trip detail") || 
        lower.includes("trip summary") || 
        lower.includes("pnr")
      )) {
        cardToShow = activeTicketContext;
      }

      setMessages(prev => [
        ...prev,
        {
          id: Date.now() + 1,
          sender: 'bot',
          provider: provider,
          text: replyText,
          structuredCard: cardToShow,
          buses: data.buses || null,
          allTickets: data.all_tickets || uploadedTickets,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        }
      ]);

    } catch (err) {
      console.warn("AI Chat API fetch failed, falling back to client-side domain intelligence:", err);
      const fallback = evaluateClientSideDomainResponse(query, activeTicketContext, uploadedTickets);
      setActiveProvider(fallback.provider);
      
      setMessages(prev => [
        ...prev,
        {
          id: Date.now() + 1,
          sender: 'bot',
          provider: fallback.provider,
          text: fallback.text,
          structuredCard: activeTicketContext,
          allTickets: uploadedTickets,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        }
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  // Real document file upload handler (Multiple PDF / TXT / Image files supported)
  const processUploadedFiles = async (filesList) => {
    const files = Array.from(filesList || []);
    if (files.length === 0) return;

    setIsUploading(true);
    const newRecords = [];
    const fileNames = files.map(f => f.name);

    // User upload bubble (Clean homepage white styling)
    setMessages(prev => [
      ...prev,
      {
        id: Date.now(),
        sender: 'user',
        text: files.length === 1 
          ? `Uploaded travel ticket: ${files[0].name}`
          : `Uploaded ${files.length} travel documents: ${fileNames.join(', ')}`,
        isFile: true,
        fileName: fileNames.join(', '),
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      }
    ]);

    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      const fileName = file.name;

      if (files.length > 1) {
        setUploadProgress(`Extracting & analyzing ${i + 1} of ${files.length}: ${fileName}...`);
      } else {
        setUploadProgress(`Extracting & analyzing ticket: ${fileName}...`);
      }

      let parsedRecord = null;

      try {
        const formData = new FormData();
        formData.append('file', file);

        const response = await fetch('/api/ai/upload-document', {
          method: 'POST',
          body: formData
        });

        if (response.ok) {
          const resData = await response.json();
          parsedRecord = resData.structured_data;
        }
      } catch (err) {
        console.warn("Server upload attempt error:", err);
      }

      if (parsedRecord) {
        newRecords.push(parsedRecord);
      }
    }

    if (newRecords.length > 0) {
      const combinedTickets = [...uploadedTickets, ...newRecords];
      setUploadedTickets(combinedTickets);
      const lastRecord = newRecords[newRecords.length - 1];
      setCurrentDisruption(lastRecord);

      // Keep user in chat! Notify DisruptionPage without redirecting!
      if (onTicketProcessed) {
        onTicketProcessed(lastRecord, combinedTickets);
      }

      if (newRecords.length === 1) {
        const parsedRecord = newRecords[0];
        const carrier = parsedRecord?.carrier || 'Carrier';
        const service = parsedRecord?.service_number || 'Transit';
        const origin = parsedRecord?.origin || 'Origin';
        const destination = parsedRecord?.destination || 'Destination';
        const delay = typeof parsedRecord?.delay_minutes === 'number' ? parsedRecord.delay_minutes : 0;
        const isPast = parsedRecord?.is_past_journey === true;
        const pnr = parsedRecord?.pnr || 'N/A';
        const fare = (parsedRecord?.ticket_cost && Number(parsedRecord.ticket_cost) > 0)
          ? `₹${Number(parsedRecord.ticket_cost).toLocaleString()} ${parsedRecord?.currency || 'INR'}`
          : 'Standard Fare';

        const statusLine = isPast
          ? '**Travel Status**: ✅ Historical Journey — Service Already Completed'
          : parsedRecord?.is_cancellation
            ? '**Travel Status**: ❌ Service Cancelled'
            : delay > 0
              ? `**Reported Disruption**: ⚠️ +${delay} mins delay`
              : '**Travel Status**: ✅ On Schedule — Running Right Time (+0m delay)';

        const extractedSummaryText = `📄 **Document Successfully Processed & Analyzed!**\n\nHere are the travel details extracted from **${files[0].name}**:\n• **Carrier & Service**: ${carrier} ${service}\n• **Route Corridor**: ${origin} ➔ ${destination}\n• ${statusLine}\n• **PNR / Booking Ref**: ${pnr}\n• **Ticket Fare**: ${fare}\n• **Statutory Protection**: ${isPast ? 'IRCTC TDR Policy — File TDR on IRCTC portal if journey was missed' : 'DGCA CAR Section 3 & EU261 active'}\n\n**What would you like to do next?**\nChoose one of the 3 actions below to upload another document, chat about your trip, or proceed to the travel map:`;

        setMessages(prev => [
          ...prev,
          {
            id: Date.now() + 1,
            sender: 'bot',
            provider: 'Voyage AI Engine',
            text: extractedSummaryText,
            structuredCard: parsedRecord,
            allTickets: combinedTickets,
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
          }
        ]);
      } else {
        // Multi-document summary card
        const legSummaries = newRecords.map((r, idx) => 
          `• **Leg ${idx + 1}**: ${r.carrier} ${r.service_number} (${r.origin} ➔ ${r.destination}) ${r.delay_minutes > 0 ? `• +${r.delay_minutes}m delay` : "• On-Time"}`
        ).join('\n');

        const multiSummaryText = `📄 **${newRecords.length} Travel Documents Successfully Analyzed & Connected!**\n\nHere is your multi-modal connected itinerary:\n${legSummaries}\n• **Corridor**: ${newRecords[0].origin} ➔ ... ➔ ${newRecords[newRecords.length - 1].destination}\n• **Domino Cascade Risk**: Evaluated via Critical Path Method (CPM)\n\n**What would you like to do next?**\nChoose one of the 3 actions below to upload another document, chat about your trip, or proceed to the travel map:`;

        setMessages(prev => [
          ...prev,
          {
            id: Date.now() + 1,
            sender: 'bot',
            provider: 'Voyage AI Engine',
            text: multiSummaryText,
            structuredCard: lastRecord,
            multiLegCard: newRecords,
            allTickets: combinedTickets,
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
          }
        ]);
      }
    } else {
      setMessages(prev => [
        ...prev,
        {
          id: Date.now() + 1,
          sender: 'bot',
          provider: 'Voyage AI Engine',
          text: `⚠️ **Document Extraction Notice**\nCould not extract travel details from the uploaded document(s). Please verify that the file contains readable ticket details (such as PNR, train/flight number, passenger name, and route) and that the backend server is reachable.`,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        }
      ]);
    }

    setIsUploading(false);
    setUploadProgress('');
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handleFileUpload = (e) => {
    processUploadedFiles(e.target.files);
  };

  // Copy code snippet helper
  const handleCopyCode = (text, id) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  // Rich text and Code Block Renderer
  const renderMessageContent = (text, msgId) => {
    if (!text) return null;

    // Check for markdown code blocks (```language ... ```)
    const codeBlockRegex = /```([a-zA-Z]*)\n([\s\S]*?)```/g;
    const parts = [];
    let lastIndex = 0;
    let match;

    while ((match = codeBlockRegex.exec(text)) !== null) {
      if (match.index > lastIndex) {
        parts.push({
          type: 'text',
          content: text.slice(lastIndex, match.index)
        });
      }

      parts.push({
        type: 'code',
        language: match[1] || 'text',
        code: match[2].trim()
      });

      lastIndex = match.index + match[0].length;
    }

    if (lastIndex < text.length) {
      parts.push({
        type: 'text',
        content: text.slice(lastIndex)
      });
    }

    if (parts.length === 0) {
      parts.push({ type: 'text', content: text });
    }

    return (
      <div className="space-y-3">
        {parts.map((part, index) => {
          if (part.type === 'code') {
            const blockId = `${msgId}-code-${index}`;
            const isCopied = copiedId === blockId;
            return (
              <div key={index} className="rounded-2xl overflow-hidden border border-slate-700/60 bg-[#0F172A] shadow-md my-2 font-mono text-[11px]">
                <div className="bg-[#1E293B] px-4 py-2 border-b border-slate-700/80 flex items-center justify-between text-slate-300">
                  <div className="flex items-center gap-2">
                    <Code className="w-3.5 h-3.5 text-[#F1A501]" />
                    <span className="font-semibold uppercase tracking-wider text-[10px] text-slate-200">
                      {part.language || 'code'}
                    </span>
                  </div>
                  <button
                    onClick={() => handleCopyCode(part.code, blockId)}
                    className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-slate-700/60 hover:bg-slate-700 text-slate-200 hover:text-white transition-colors cursor-pointer text-[10px]"
                  >
                    {isCopied ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                    <span>{isCopied ? "Copied" : "Copy Code"}</span>
                  </button>
                </div>
                <pre className="p-4 text-emerald-300 overflow-x-auto leading-relaxed whitespace-pre font-mono">
                  <code>{part.code}</code>
                </pre>
              </div>
            );
          }

          // Plain text rendering with bullet points and bold formatting
          return (
            <div key={index} className="whitespace-pre-line leading-relaxed">
              {part.content.split('\n').map((line, lIdx) => {
                if (line.startsWith('### ')) {
                  return (
                    <h4 key={lIdx} className="font-volkhov font-bold text-sm text-[#181E4B] mt-2 mb-1">
                      {line.replace('### ', '')}
                    </h4>
                  );
                }
                if (line.startsWith('#### ')) {
                  return (
                    <h5 key={lIdx} className="font-volkhov font-semibold text-xs text-[#181E4B] mt-1.5 mb-1">
                      {line.replace('#### ', '')}
                    </h5>
                  );
                }
                return (
                  <p key={lIdx} className={line.startsWith('•') || line.startsWith('-') ? 'pl-2 text-[#181E4B]' : 'text-[#181E4B]'}>
                    {renderFormattedLine(line)}
                  </p>
                );
              })}
            </div>
          );
        })}
      </div>
    );
  };

  // Helper for bold text (**text**)
  const renderFormattedLine = (line) => {
    const boldRegex = /\*\*(.*?)\*\*/g;
    const parts = [];
    let lastIndex = 0;
    let match;

    while ((match = boldRegex.exec(line)) !== null) {
      if (match.index > lastIndex) {
        parts.push(line.slice(lastIndex, match.index));
      }
      parts.push(
        <strong key={match.index} className="font-semibold text-[#181E4B]">
          {match[1]}
        </strong>
      );
      lastIndex = match.index + match[0].length;
    }

    if (lastIndex < line.length) {
      parts.push(line.slice(lastIndex));
    }

    return parts.length > 0 ? parts : line;
  };

  // Drag and drop handlers
  const handleDragOver = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      processUploadedFiles(e.dataTransfer.files);
    }
  };

  // Collapsed Pill Button in bottom right
  if (isMinimized) {
    return (
      <div className="fixed bottom-6 right-6 z-40 animate-in fade-in zoom-in-95 duration-200">
        <button
          onClick={onRestore}
          className="flex items-center gap-2.5 px-5 py-3 rounded-full bg-[#181E4B] text-white shadow-xl hover:bg-[#232a68] border border-white/20 transition-all hover:scale-105 active:scale-95 cursor-pointer font-googleSans text-xs font-bold"
        >
          <div className="relative">
            <Bot className="w-4 h-4 text-[#F1A501]" />
            <span className="absolute -top-1 -right-1 w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
          </div>
          <span>Voyage AI Assistant</span>
          {uploadedTickets.length > 0 && (
            <span className="px-2 py-0.5 rounded-full text-[10px] font-mono bg-[#DF6951] text-white">
              {uploadedTickets.length}
            </span>
          )}
        </button>
      </div>
    );
  }

  return (
    <div
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      className={`relative transition-all duration-300 font-poppins ${
        isFloating
          ? "fixed bottom-6 right-6 z-40 w-[95vw] sm:w-[460px] h-[600px] max-h-[calc(100vh-120px)] rounded-3xl bg-white shadow-2xl border border-slate-200/90 flex flex-col overflow-hidden animate-in fade-in slide-in-from-bottom-6"
          : "w-full min-h-[500px] h-[620px] rounded-3xl bg-white shadow-sm border border-slate-200/90 flex flex-col overflow-hidden"
      }`}
    >
      {/* Drag & Drop Visual Overlay */}
      {isDragging && (
        <div className="absolute inset-0 z-40 bg-purple-900/80 backdrop-blur-xs flex flex-col items-center justify-center text-white p-6 border-4 border-dashed border-white rounded-3xl animate-in fade-in duration-150">
          <UploadCloud className="w-14 h-14 text-purple-200 animate-bounce mb-3" />
          <h3 className="font-volkhov font-bold text-xl">Drop Ticket Documents Here</h3>
          <p className="text-xs text-purple-200 mt-1 text-center max-w-xs">
            Drop single or multiple PDFs, images, or boarding passes to instantly extract trip details.
          </p>
        </div>
      )}

      {/* Top Header */}
      <div className="p-4 sm:p-5 border-b border-slate-200/80 bg-white flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-2xl bg-[#FFF1DA] text-[#F1A501] flex items-center justify-center shadow-xs">
            <Sparkles className="w-5 h-5 text-[#DF6951]" />
          </div>
          <div>
            <h3 className="font-volkhov font-bold text-sm sm:text-base text-[#181E4B]">
              Voyage Travel Concierge
            </h3>
            <p className="text-[11px] text-[#5E6282] mt-0.5">
              Multi-Modal Delay Recovery &amp; Statutory Compensation Engine
            </p>
          </div>
        </div>

        <div className="flex items-center gap-1">
          <button
            onClick={() => setShowSettings(!showSettings)}
            className="p-2 rounded-xl text-slate-400 hover:text-[#181E4B] hover:bg-slate-100 transition-colors cursor-pointer"
            title="Configure AI API Keys"
          >
            <Key className="w-4 h-4" />
          </button>

          <button
            onClick={handleClearChat}
            className="p-2 rounded-xl text-slate-400 hover:text-rose-600 hover:bg-rose-50 transition-colors cursor-pointer"
            title="Clear Chat History"
          >
            <Trash2 className="w-4 h-4" />
          </button>

          {isFloating && (
            <button
              onClick={onMinimize}
              className="p-2 rounded-xl text-slate-400 hover:text-[#181E4B] hover:bg-slate-100 transition-colors cursor-pointer"
              title="Minimize Chat"
            >
              <Minimize2 className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>

      {/* Settings Panel Drawer */}
      {showSettings && (
        <div className="p-4 bg-slate-50 border-b border-slate-200 text-xs animate-in slide-in-from-top duration-200">
          <div className="flex items-center justify-between pb-2 border-b border-slate-200">
            <span className="font-bold text-[#181E4B]">AI Provider Configuration</span>
            <button
              onClick={() => setShowSettings(false)}
              className="text-slate-400 hover:text-slate-600 cursor-pointer"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>

          <form onSubmit={handleSaveKeys} className="mt-3 space-y-3">
            <div>
              <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                Groq API Key (Llama 3.3 70B Versatile):
              </label>
              <input
                type="password"
                value={groqKey}
                onChange={(e) => setGroqKey(e.target.value)}
                placeholder="gsk_..."
                className="w-full px-3 py-2 rounded-xl border border-slate-200 focus:outline-none focus:border-[#181E4B] font-mono text-xs"
              />
            </div>
            <div>
              <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                Google Gemini API Key (Gemini 2.5 Flash):
              </label>
              <input
                type="password"
                value={geminiKey}
                onChange={(e) => setGeminiKey(e.target.value)}
                placeholder="AIzaSy..."
                className="w-full px-3 py-2 rounded-xl border border-slate-200 focus:outline-none focus:border-[#181E4B] font-mono text-xs"
              />
            </div>
            <div className="flex items-center justify-between pt-2">
              <span className="text-[10px] text-slate-400">
                Failover: Groq ➔ Gemini ➔ Voyage Local Resilience Engine.
              </span>
              <button
                type="submit"
                className="px-4 py-2 rounded-xl font-googleSans font-bold text-xs text-white bg-[#181E4B] hover:bg-[#232a68] transition-colors cursor-pointer"
              >
                Save Keys
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Messages Thread */}
      <div ref={chatContainerRef} className="flex-1 p-4 sm:p-6 overflow-y-auto space-y-4 font-poppins text-xs bg-[#FAF9F6]/40">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex ${msg.sender === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`max-w-[85%] sm:max-w-[80%] rounded-2xl p-4 leading-relaxed transition-all ${
                msg.sender === 'user'
                  ? 'bg-white text-[#181E4B] border border-slate-200/90 shadow-sm rounded-tr-xs'
                  : 'bg-[#FAF9F6] text-[#181E4B] border border-slate-200/80 rounded-tl-xs shadow-2xs'
              }`}
            >
              {/* User Identity Label */}
              {msg.sender === 'user' && (
                <div className="flex items-center justify-end gap-1.5 mb-1.5 pb-1 border-b border-slate-100 text-[10px] font-semibold text-[#84829A] font-mono">
                  <span>You</span>
                </div>
              )}

              {/* Bot Provider Label */}
              {msg.provider && msg.sender === 'bot' && (
                <div className="flex items-center gap-1.5 mb-2 pb-1.5 border-b border-slate-200/60 text-[10px] font-mono text-[#5E6282]">
                  <Sparkles className="w-3 h-3 text-[#F1A501]" />
                  <span>{msg.provider}</span>
                </div>
              )}

              {/* Attached file badge inside user chat */}
              {msg.isFile && (
                <div className="flex items-center gap-2 mb-2 p-2.5 bg-slate-50 border border-slate-200/80 rounded-xl text-[#181E4B]">
                  <div className="p-1 rounded-lg bg-orange-100/80 text-[#DF6951]">
                    <FileText className="w-4 h-4" />
                  </div>
                  <span className="font-mono text-xs font-semibold text-[#181E4B]">{msg.fileName}</span>
                  <span className="ml-auto text-[10px] font-mono font-bold text-slate-400 bg-white px-2 py-0.5 rounded border border-slate-200">
                    DOCUMENT
                  </span>
                </div>
              )}

              {renderMessageContent(msg.text, msg.id)}

              {/* Ingested Ticket Card with 3 Explicit Actions (Upload Another / Chat / Done) */}
              {msg.structuredCard && (
                <div className="mt-4 pt-3.5 border-t border-slate-200/80 space-y-3 font-poppins">
                  
                  {/* Clean Trip Header Card matching homepage aesthetic */}
                  <div className="p-3.5 bg-white rounded-2xl border border-slate-200/90 shadow-2xs space-y-2.5">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <div className="w-7 h-7 rounded-xl bg-[#FFF1DA] text-[#DF6951] flex items-center justify-center font-bold">
                          {msg.structuredCard.carrier?.toLowerCase().includes("rail") || msg.structuredCard.carrier?.toLowerCase().includes("train") ? (
                            <Train className="w-4 h-4" />
                          ) : (
                            <Plane className="w-4 h-4" />
                          )}
                        </div>
                        <div>
                          <span className="font-bold text-xs text-[#181E4B]">
                            {msg.structuredCard.carrier} ({msg.structuredCard.service_number})
                          </span>
                          <span className="text-[10px] text-[#5E6282] block font-mono">
                            PNR: {msg.structuredCard.pnr}
                          </span>
                        </div>
                      </div>

                      <span className={`px-2.5 py-1 rounded-full text-[10px] font-mono font-bold ${
                        isPastTicket(msg.structuredCard) 
                          ? "bg-slate-100 text-slate-700 border border-slate-200" 
                          : (msg.structuredCard.delay_minutes > 0 ? "bg-amber-100 text-amber-900 border border-amber-200" : "bg-white text-slate-800 border border-slate-300 shadow-2xs")
                      }`}>
                        {isPastTicket(msg.structuredCard) 
                          ? "PAST TRIP (COMPLETED)" 
                          : (msg.structuredCard.delay_minutes > 0 ? `+${msg.structuredCard.delay_minutes}m DELAY` : "ON-TIME")}
                      </span>
                    </div>

                    <div className="p-2.5 rounded-xl bg-slate-50 border border-slate-100 flex items-center justify-between text-xs">
                      <div className="flex items-center gap-2 font-semibold text-[#181E4B]">
                        <span>{msg.structuredCard.origin}</span>
                        <ArrowRight className="w-3.5 h-3.5 text-[#DF6951]" />
                        <span>{msg.structuredCard.destination}</span>
                      </div>
                      <span className="text-[10px] font-mono font-semibold text-[#5E6282]">
                        {msg.structuredCard.ticket_cost ? `₹${msg.structuredCard.ticket_cost}` : "Standard Fare"}
                      </span>
                    </div>

                    {/* Historical Travel Notice if ticket date is in the past */}
                    {isPastTicket(msg.structuredCard) && (
                      <div className="p-2.5 rounded-xl bg-slate-50 border border-slate-200 text-[11px] text-slate-600 flex items-start gap-2">
                        <Clock className="w-4 h-4 text-slate-500 shrink-0 mt-0.5" />
                        <div>
                          <strong className="text-slate-800 font-semibold">Historical Journey ({msg.structuredCard.travel_date || "Past Date"}):</strong> This service has already completed its scheduled run. You can chat below to discuss if you caught this train or explore IRCTC TDR refund rules.
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Multi-Leg Journey Details if multiple documents uploaded */}
                  {msg.multiLegCard && msg.multiLegCard.length > 1 && (
                    <div className="p-3 rounded-2xl bg-purple-50/70 border border-purple-200/80 space-y-2">
                      <div className="text-xs font-bold text-purple-900 flex items-center gap-1.5">
                        <Layers className="w-3.5 h-3.5 text-purple-700" />
                        <span>Connected Journey Legs ({msg.multiLegCard.length} Documents)</span>
                      </div>
                      <div className="space-y-1.5 text-[11px] font-mono">
                        {msg.multiLegCard.map((leg, idx) => (
                          <div key={idx} className="flex items-center justify-between p-2 bg-white rounded-xl border border-purple-100">
                            <div>
                              <span className="font-bold text-slate-800">Leg {idx + 1}: {leg.carrier} {leg.service_number}</span>
                              <div className="text-[10px] text-slate-500">{leg.origin} ➔ {leg.destination}</div>
                            </div>
                            <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                              isPastTicket(leg) 
                                ? "bg-slate-100 text-slate-700 border border-slate-200" 
                                : (leg.delay_minutes > 0 ? "bg-amber-100 text-amber-800 border border-amber-200" : "bg-white text-slate-800 border border-slate-300 shadow-2xs")
                            }`}>
                              {isPastTicket(leg) ? "COMPLETED" : (leg.delay_minutes > 0 ? `+${leg.delay_minutes}m` : "ON-TIME")}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* THREE PROMINENT OPTIONS REQUESTED BY USER */}
                  <div className="space-y-1.5 pt-1">
                    <div className="text-[11px] font-bold text-[#181E4B] flex items-center gap-1.5">
                      <Sparkles className="w-3.5 h-3.5 text-[#F1A501]" />
                      <span>Choose next action:</span>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 pt-1">
                      
                      {/* OPTION 1: Upload Another */}
                      <button
                        type="button"
                        onClick={() => fileInputRef.current?.click()}
                        className="p-2.5 rounded-xl bg-white hover:bg-slate-50 border border-slate-300/80 hover:border-slate-400 text-[#181E4B] font-googleSans text-xs font-bold transition-all cursor-pointer flex flex-col items-center justify-center gap-1 shadow-2xs group text-center"
                      >
                        <div className="w-7 h-7 rounded-lg bg-purple-50 group-hover:bg-purple-100 text-purple-700 flex items-center justify-center transition-colors">
                          <UploadCloud className="w-4 h-4" />
                        </div>
                        <span>Upload Another</span>
                        <span className="text-[9px] font-normal text-[#84829A]">Add train, flight or bus</span>
                      </button>

                      {/* OPTION 2: Chat */}
                      <button
                        type="button"
                        onClick={() => {
                          textInputRef.current?.focus();
                          if (msg.structuredCard.is_past_journey) {
                            setInputText(`Did I catch ${msg.structuredCard.carrier} ${msg.structuredCard.service_number} on ${msg.structuredCard.travel_date || 'my travel date'}? Is the train still running or already completed?`);
                          } else {
                            setInputText(`Give complete details and refund rights for my ${msg.structuredCard.carrier} ${msg.structuredCard.service_number} trip`);
                          }
                        }}
                        className="p-2.5 rounded-xl bg-white hover:bg-slate-50 border border-slate-300/80 hover:border-slate-400 text-[#181E4B] font-googleSans text-xs font-bold transition-all cursor-pointer flex flex-col items-center justify-center gap-1 shadow-2xs group text-center"
                      >
                        <div className="w-7 h-7 rounded-lg bg-blue-50 group-hover:bg-blue-100 text-blue-700 flex items-center justify-center transition-colors">
                          <MessageSquare className="w-4 h-4" />
                        </div>
                        <span>Chat about Trip</span>
                        <span className="text-[9px] font-normal text-[#84829A]">{msg.structuredCard.is_past_journey ? "Check train status & rights" : "Ask rights & delay details"}</span>
                      </button>

                      {/* OPTION 3: Done -> Redirect to Travel Map (Clean White Styling) */}
                      <button
                        type="button"
                        onClick={() => {
                          if (onProceedToMap) {
                            onProceedToMap(msg.structuredCard, msg.allTickets || uploadedTickets);
                          } else if (onEndChat) {
                            onEndChat(msg.structuredCard);
                          }
                        }}
                        className="p-2.5 rounded-xl bg-white hover:bg-emerald-50/70 text-[#181E4B] border-2 border-emerald-500 font-googleSans text-xs font-bold transition-all cursor-pointer flex flex-col items-center justify-center gap-1 shadow-sm group text-center"
                      >
                        <div className="w-7 h-7 rounded-lg bg-emerald-100 text-emerald-700 flex items-center justify-center transition-colors">
                          <Check className="w-4 h-4 text-emerald-600" />
                        </div>
                        <span className="flex items-center gap-1 font-bold text-[#181E4B]">
                          Done (View Map) <ArrowRight className="w-3 h-3 text-emerald-600" />
                        </span>
                        <span className="text-[9px] font-normal text-[#5E6282]">Redirect to Travel Map</span>
                      </button>

                    </div>
                  </div>
                </div>
              )}

              {/* Structured Intercity Bus Departures Card */}
              {msg.buses && msg.buses.length > 0 && (
                <div className="mt-4 pt-3.5 border-t border-slate-200/80 space-y-3 font-poppins">
                  <div className="p-3.5 bg-white rounded-2xl border border-slate-200/90 shadow-2xs space-y-3">
                    
                    {/* Header */}
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2.5">
                        <div className="w-8 h-8 rounded-xl bg-[#FFF1DA] text-[#DF6951] flex items-center justify-center font-bold">
                          <Bus className="w-4 h-4" />
                        </div>
                        <div>
                          <span className="font-bold text-xs text-[#181E4B] block">
                            {msg.buses[0]?.origin_point?.replace(/\s*\([^)]*\)/g, '').trim()} ➔ {msg.buses[0]?.drop_point?.replace(/\s*\([^)]*\)/g, '').trim()}
                          </span>
                          <span className="text-[10px] text-[#5E6282] font-mono">
                            {msg.buses.length} Verified Services (MSRTC & Premier Sleeper)
                          </span>
                        </div>
                      </div>
                      <span className="px-2.5 py-1 rounded-full text-[10px] font-mono font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
                        VERIFIED TIMETABLE
                      </span>
                    </div>

                    {/* Time of Day Inquiry with Quick Chips */}
                    <div className="p-2.5 rounded-xl bg-[#FAF9F6] border border-slate-200/70 space-y-2">
                      <div className="flex items-center gap-1.5 text-xs font-bold text-[#181E4B]">
                        <Clock className="w-3.5 h-3.5 text-[#DF6951]" />
                        <span>What time do you plan to depart?</span>
                      </div>
                      <p className="text-[11px] text-[#5E6282]">
                        Filter departures by your preferred travel window:
                      </p>
                      <div className="flex flex-wrap gap-1.5 pt-0.5">
                        <button
                          type="button"
                          onClick={() => handleSendMessage(`Show me morning departures between 6 AM and 12 PM for ${msg.buses[0]?.origin_point?.split(' ')[0]} to ${msg.buses[0]?.drop_point?.split(' ')[0]}`)}
                          className="px-2.5 py-1 rounded-lg text-[10.5px] font-semibold bg-white hover:bg-[#FFF1DA] text-[#181E4B] hover:text-[#DF6951] border border-slate-200 hover:border-[#DF6951]/40 transition shadow-2xs flex items-center gap-1 cursor-pointer active:scale-95"
                        >
                          <Sunrise className="w-3 h-3 text-amber-500" />
                          <span>Morning (06:00–12:00)</span>
                        </button>
                        <button
                          type="button"
                          onClick={() => handleSendMessage(`Show me afternoon departures between 12 PM and 6 PM for ${msg.buses[0]?.origin_point?.split(' ')[0]} to ${msg.buses[0]?.drop_point?.split(' ')[0]}`)}
                          className="px-2.5 py-1 rounded-lg text-[10.5px] font-semibold bg-white hover:bg-[#FFF1DA] text-[#181E4B] hover:text-[#DF6951] border border-slate-200 hover:border-[#DF6951]/40 transition shadow-2xs flex items-center gap-1 cursor-pointer active:scale-95"
                        >
                          <Sun className="w-3 h-3 text-orange-500" />
                          <span>Afternoon (12:00–18:00)</span>
                        </button>
                        <button
                          type="button"
                          onClick={() => handleSendMessage(`Show me overnight sleeper buses after 8 PM for ${msg.buses[0]?.origin_point?.split(' ')[0]} to ${msg.buses[0]?.drop_point?.split(' ')[0]}`)}
                          className="px-2.5 py-1 rounded-lg text-[10.5px] font-semibold bg-white hover:bg-[#FFF1DA] text-[#181E4B] hover:text-[#DF6951] border border-slate-200 hover:border-[#DF6951]/40 transition shadow-2xs flex items-center gap-1 cursor-pointer active:scale-95"
                        >
                          <Moon className="w-3 h-3 text-indigo-500" />
                          <span>Night Sleeper (18:00+)</span>
                        </button>
                        <button
                          type="button"
                          onClick={() => handleSendMessage(`Show the cheapest bus options under ₹400 for ${msg.buses[0]?.origin_point?.split(' ')[0]} to ${msg.buses[0]?.drop_point?.split(' ')[0]}`)}
                          className="px-2.5 py-1 rounded-lg text-[10.5px] font-semibold bg-white hover:bg-emerald-50 text-[#181E4B] hover:text-emerald-700 border border-slate-200 hover:border-emerald-300 transition shadow-2xs cursor-pointer active:scale-95"
                        >
                          <span>💰 Lowest Fare</span>
                        </button>
                      </div>
                    </div>

                    {/* Departures Grid */}
                    <div className="space-y-2">
                      {msg.buses.map((bus, bIdx) => (
                        <div 
                          key={bIdx}
                          className="p-3 rounded-xl bg-slate-50/80 border border-slate-200 hover:border-slate-300 transition flex flex-col sm:flex-row sm:items-center justify-between gap-2.5"
                        >
                          <div className="space-y-1 min-w-0">
                            <div className="flex items-center gap-2 flex-wrap">
                              <span className="font-bold text-xs text-[#181E4B]">{bus.operator}</span>
                              <span className="px-2 py-0.5 rounded text-[9px] font-semibold bg-white text-slate-700 border border-slate-200">
                                {bus.bus_type}
                              </span>
                              {bus.rating && (
                                <span className="text-[10px] text-amber-600 font-bold flex items-center gap-0.5">
                                  ⭐ {bus.rating}
                                </span>
                              )}
                            </div>

                            <div className="text-[11px] text-[#5E6282] flex items-center gap-1.5 flex-wrap">
                              <span className="font-bold text-slate-900 font-mono">{bus.departure_time}</span>
                              <span className="text-[10px] text-slate-500">({bus.origin_point})</span>
                              <ArrowRight className="w-3 h-3 text-[#DF6951]" />
                              <span className="font-bold text-slate-900 font-mono">{bus.arrival_time}</span>
                              <span className="text-[10px] text-slate-500">({bus.drop_point})</span>
                            </div>

                            {bus.route && (
                              <div className="text-[10px] text-slate-500">
                                🛣️ {bus.route}
                              </div>
                            )}
                          </div>

                          <div className="flex sm:flex-col items-center sm:items-end justify-between sm:justify-center gap-1.5 shrink-0 pt-1 sm:pt-0 border-t sm:border-t-0 border-slate-200/60">
                            <div className="text-left sm:text-right">
                              <span className="font-mono font-extrabold text-sm text-[#181E4B]">₹{bus.fare_inr}</span>
                              <span className="text-[10px] text-[#84829A] block font-mono">{bus.duration}</span>
                            </div>
                            <a
                              href={bus.booking_link || "https://npublic.msrtcors.com"}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg text-[10.5px] font-bold text-white bg-[#181E4B] hover:bg-[#28327a] transition shadow-2xs"
                            >
                              <span>Book</span>
                              <ExternalLink className="w-3 h-3" />
                            </a>
                          </div>
                        </div>
                      ))}
                    </div>

                  </div>
                </div>
              )}

              {/* Timestamp */}
              <span className={`text-[10px] mt-2 block font-mono ${msg.sender === 'user' ? 'text-slate-400 text-right' : 'text-slate-400'}`}>
                {msg.timestamp}
              </span>
            </div>
          </div>
        ))}

        {/* AI Typing Indicator */}
        {isLoading && (
          <div className="flex justify-start">
            <div className="p-3.5 rounded-2xl bg-white border border-slate-200 text-[#181E4B] flex items-center gap-2 shadow-2xs">
              <span className="w-2 h-2 rounded-full bg-[#181E4B] animate-bounce" style={{ animationDelay: '0ms' }} />
              <span className="w-2 h-2 rounded-full bg-[#181E4B] animate-bounce" style={{ animationDelay: '150ms' }} />
              <span className="w-2 h-2 rounded-full bg-[#181E4B] animate-bounce" style={{ animationDelay: '300ms' }} />
              <span className="text-[11px] font-mono text-slate-500 ml-1">Analyzing trip...</span>
            </div>
          </div>
        )}

        {/* Live Audio Waves when recording */}
        {isRecording && (
          <div className="flex items-center gap-3 p-4 rounded-2xl bg-amber-50 border border-amber-200 text-amber-900 animate-pulse">
            <Volume2 className="w-5 h-5 text-amber-600" />
            <div className="flex-1">
              <div className="font-bold text-xs">Listening to your voice... Speak your flight disruption or question</div>
              <div className="flex items-center gap-1 mt-1.5 h-4">
                <span className="w-1 bg-amber-600 h-2 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                <span className="w-1 bg-amber-600 h-4 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                <span className="w-1 bg-amber-600 h-3 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                <span className="w-1 bg-amber-600 h-5 rounded-full animate-bounce" style={{ animationDelay: '450ms' }} />
                <span className="w-1 bg-amber-600 h-2 rounded-full animate-bounce" style={{ animationDelay: '200ms' }} />
              </div>
            </div>
            <button
              onClick={toggleVoiceRecording}
              className="text-xs font-bold text-amber-800 hover:text-amber-950 underline cursor-pointer"
            >
              Stop
            </button>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Toolbar */}
      <div className="p-4 bg-white border-t border-slate-200">
        {/* Post-Upload Sticky Action Bar if a ticket is loaded */}
        {(currentDisruption || uploadedTickets.length > 0) && (
          <div className="flex flex-wrap items-center justify-between gap-2 pb-2.5 mb-2.5 border-b border-slate-100 text-xs font-poppins">
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                className="flex items-center gap-1.5 px-3 py-1 rounded-xl text-[11px] font-semibold bg-purple-50 text-purple-800 hover:bg-purple-100 border border-purple-200 transition-all cursor-pointer shadow-2xs"
              >
                <UploadCloud className="w-3.5 h-3.5 text-purple-700" />
                <span>+ Upload Another</span>
              </button>

              <button
                type="button"
                onClick={() => {
                  textInputRef.current?.focus();
                  setInputText("Give full detail about my trip and compensation eligibility");
                }}
                className="flex items-center gap-1.5 px-3 py-1 rounded-xl text-[11px] font-semibold bg-blue-50 text-blue-800 hover:bg-blue-100 border border-blue-200 transition-all cursor-pointer shadow-2xs"
              >
                <MessageSquare className="w-3.5 h-3.5 text-blue-700" />
                <span>Chat about Trip</span>
              </button>
            </div>

            <div className="flex items-center gap-2 text-[11px] text-slate-500">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
              <span className="font-medium text-slate-700">
                {uploadedTickets.length > 1
                  ? `${uploadedTickets.length} Tickets Connected`
                  : `${currentDisruption?.carrier} ${currentDisruption?.service_number} (${currentDisruption?.origin} ➔ ${currentDisruption?.destination})`}
              </span>
              <span className="text-slate-300">•</span>
              <button
                type="button"
                onClick={() => {
                  if (onProceedToMap) {
                    onProceedToMap(currentDisruption, uploadedTickets);
                  } else if (onEndChat) {
                    onEndChat(currentDisruption);
                  }
                }}
                className="px-3 py-1 rounded-xl bg-[#181E4B] hover:bg-[#232a68] text-white font-bold transition-all cursor-pointer flex items-center gap-1 shadow-2xs text-[11px]"
              >
                <span>Done (View Map)</span>
                <ArrowRight className="w-3 h-3 text-[#DF6951]" />
              </button>
            </div>
          </div>
        )}

        {isUploading && uploadProgress && (
          <div className="mb-2 text-[11px] text-purple-700 bg-purple-50 px-3 py-1.5 rounded-xl border border-purple-200 flex items-center gap-2 animate-pulse">
            <UploadCloud className="w-3.5 h-3.5 animate-bounce" />
            <span className="font-semibold">{uploadProgress}</span>
          </div>
        )}

        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSendMessage();
          }}
          className="flex items-center gap-2"
        >
          {/* File Upload Input (PDF, PNG, JPG, TXT) with multiple file support */}
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileUpload}
            accept=".pdf,.png,.jpg,.jpeg,.txt"
            multiple
            className="hidden"
          />

          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={isUploading}
            className="p-2.5 rounded-xl text-slate-500 hover:text-[#181E4B] hover:bg-slate-100 transition-colors cursor-pointer shrink-0 disabled:opacity-50"
            title="Upload Ticket or Boarding Pass (PDF / Image / Text)"
          >
            <Paperclip className="w-4 h-4" />
          </button>

          <button
            type="button"
            onClick={toggleVoiceRecording}
            className={`p-2.5 rounded-xl transition-all cursor-pointer shrink-0 ${
              isRecording
                ? "bg-rose-500 text-white animate-pulse"
                : "text-slate-500 hover:text-[#181E4B] hover:bg-slate-100"
            }`}
            title={isRecording ? "Stop voice listening" : "Speak your message"}
          >
            {isRecording ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
          </button>

          <input
            ref={textInputRef}
            type="text"
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            placeholder="Type your message, ask about delays, or drag tickets here..."
            className="flex-1 px-4 py-2.5 rounded-xl bg-slate-50 border border-slate-200/80 focus:outline-none focus:border-[#181E4B] focus:bg-white text-xs font-poppins text-[#181E4B] placeholder:text-slate-400 transition-all"
          />

          <button
            type="submit"
            disabled={!inputText.trim() || isLoading}
            className="p-2.5 rounded-xl bg-[#181E4B] hover:bg-[#232a68] text-white disabled:opacity-40 transition-all cursor-pointer shrink-0 shadow-xs"
          >
            <Send className="w-4 h-4" />
          </button>
        </form>
      </div>
    </div>
  );
}
