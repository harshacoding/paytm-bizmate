# What should Paytm build for the AI hackathon?

**Competitive intelligence and product decision brief · India · 8 November 2026**

## Part 1. Executive summary

**Build Hisab Saathi, a settlement investigation teammate for Paytm merchant support.** Give it one concrete job. When a shopkeeper says yesterday’s collection and today’s bank credit disagree, trace the difference to individual entries, explain it in the merchant’s language, and keep any unsupported amount open with a named owner. The demo should end with a balanced close or a documented handoff. A Paytm merchant described having to calculate manually which day’s sales had settled. Paytm’s own missing-payout instructions ask the merchant to consult both the settlements tab and the bank statement. [S81][S81] [S11][S11]

**The strongest competitive objection is Razorpay Recon.** Razorpay already announced AI reconciliation across payment, POS, bank and cash records in December 2024. Paytm already provides transaction-level settlement data, scheduled reports, an AI Soundbox, and an authorized ChatGPT integration that answers settlement and refund questions. Pitch the additional job narrowly: investigate a merchant’s support case across a bank credit and Paytm’s books, show the evidence for each rupee, then follow the exception to closure. Public sources establish adjacency. They leave room for a merchant usability test before claiming differentiation. [S53][S53] [S09][S09] [S08][S08] [S05][S05] [S04][S04]

**Why this problem suits Paytm.** Paytm reported 1.64 crore merchants on subscription plans and ₹7.1 lakh crore in merchant GMV in Q2 FY27. Its merchant app is a plausible entry point and its support team a plausible first buyer. Neither figure measures reconciliation demand. The commercial test is whether eligible cases consume fewer support minutes and merchants reopen fewer of them. Rank 2, Payment Relay, addresses conflicting payer and merchant records. Rank 3, Margin Diary, tackles supplier-cost changes for restaurants and has the strongest direct merchant-growth story. [S03][S03] [S12][S12] [S82][S82] [S45][S45]

**Hackathon fit.** The organizer describes the autonomous track as end-to-end sales or customer service with actions across systems and human escalation. Submit Hisab Saathi as the teammate of a merchant support operator. The Hyderabad listing gives 13–14 November 2026 as its event window and 11 November as the registration close. The Bengaluru edition ran on 31 October. The 48-hour plan below is a build budget from the brief. Individual editions set their own schedules and submission requirements. [S01][S01] [S02][S02]

## Part 2. Competitive landscape

The table separates the documented product journey from reviewer experience and from the proposed Paytm adaptation. Review observations are illustrative, sometimes about the wider app. A blank side of the feedback record means the sample did not substantiate it. Current help pages establish a documented capability in the cited market. Launch announcements, historic reviews and discontinued partnerships are identified where relevant. Business models below describe the relevant customer relationship or product line.

**Terms used below.** UPI is the Unified Payments Interface. A PSP is a payment service provider. A UTR is a unique transaction reference for a bank transfer. A merchant batch settlement can cover many individual sales, each with its own identifier. POS means point of sale. An SIP is a systematic investment plan. A mandate authorizes recurring debits, and a chargeback is a formal dispute processed through the relevant payment channel.

### India

| Company and segment | Product journey and business context | Customer feedback in the sample | Implication for Paytm |
|---|---|---|---|
| PhonePe · shopkeepers and UPI users | A merchant accepts a payment and hears a local-language SmartSpeaker confirmation at the counter. | A consumer described duplicate-looking mandates after repeated setup attempts and difficulty pausing them. This concerns AutoPay, separate from the speaker. | Preserve instant audio at checkout. Move ambiguous mandate states and settlement exceptions into a recoverable workflow. [S46][S46] [S88][S88] |
| Google Pay India · UPI consumers | The user opens a merchant payment, checks status and is directed to the merchant or bank for particular exceptions. | A reviewer struggled to reopen recent payment conversations. A café customer described a GPay success opposite a failed Paytm POS entry. | Carry the reference and evidence across the handoff. A readable history alone cannot settle a cross-provider disagreement. [S47][S47] [S89][S89] [S82][S82] |
| Amazon Pay India · shoppers and bill payers | A shopper moves from commerce into recharge, bills or wallet payments inside the Amazon ecosystem. | A shopping review described a dispute over proof when a damaged item arrived. Payment-specific praise or failure cannot be inferred from that review. | Connect order, return and refund evidence only when the merchant shares the order context. [S49][S49] [S90][S90] |
| CRED · cardholders | CRED Protect detects statements and bills, surfaces fees and EMIs, and reminds members before payment. | One long-time user reported earlier trouble-free use and later difficulty tracing a card-bill payment near its due date. | Show proof that a specific obligation was posted, with separate dates for initiation and biller acknowledgement. [S50][S50] [S91][S91] |
| BharatPe · merchants and borrowers | A merchant accepts through a device, with access to facilitated credit and daily-collection terms where applicable. | A merchant reported that an unusable terminal and a delayed technician visit made inactivity especially frustrating. | Join device incidents to service ownership and the applicable fee history. Verify the merchant’s own plan. [S51][S51] [S52][S52] [S92][S92] |
| Razorpay · online sellers, POS merchants and finance teams | Recon ingests files across channels. Its API exposes payments, refunds, transfers and adjustments for a settlement period. | A seller praised earlier responsiveness and described contradictory onboarding messages. This is feedback about service, not a test of Recon. | Treat Razorpay as a direct reconciliation benchmark. Test whether a single-shop owner can close an exception unaided. [S53][S53] [S54][S54] [S93][S93] |
| Pine Labs · POS merchants and chains | Pine Labs One lets staff oversee stores, payments and settlements and upload chargeback documents. | One reviewer praised setup and support. Another reported POS interruptions and disputed charges. | Give staff store-scoped access, an evidence checklist and a service owner when a terminal fails. [S56][S56] [S94][S94] |
| MobiKwik · consumers using wallet, bills and financial services | LENS aggregates account information to give a broader financial view. | A previously enthusiastic wallet user described poor visibility after reporting an unauthorized transaction. The report concerns the wallet, not LENS. | Make evidence and case ownership visible after a report, and keep account-data consent specific to the task. [S57][S57] [S95][S95] |
| Navi · digital borrowers | Navi Finserv identifies its digital lending application. A borrower enters a lender-specific application and servicing relationship. | Reviews include praise for access to credit and complaints about the experience after missed payments. These are self-reports from earlier product versions. | Explain repayment consequences before acceptance and identify the responsible lender for servicing. [S58][S58] [S96][S96] |
| Groww · investors | After a scheduled SIP fails to debit, the help path checks the bank and offers a ticket. | A beginner praised the investment interface. A separate reviewer described losing access during re-KYC. | Explain the difference between an active mandate, a due instalment, a bank debit and a completed investment order. [S59][S59] [S97][S97] |
| Jupiter · personal banking and budgeting users | Spend Insights groups transactions and Pots earmark money for goals in partner-led banking. | Reviews praise the interface and describe difficulty resolving an active-mandate disagreement with support. | Attach source events and a correction path to any prediction about a future debit. [S60][S60] [S87][S87] [S98][S98] |
| Fi Money · former partner-bank app users | Ask.Fi offered conversational spending search. Federal Bank says the partnership ended on 31 March 2026. Fi says new savings accounts cannot be opened in the app. | Users recalled liking expense tracking and asked how the transition would affect access. | Historical design precedent. Show the data source, last refresh and an export path when a financial connection ends. [S61][S61] [S62][S62] [S63][S63] [S86][S86] |
| INDmoney · investors and families | Members can share selected information, see separate portfolios and inspect combined family wealth. | Reviewers praised the consolidated view and autonomy. No family-permission failure was established in the reviewed material. | Give household members control over what they share. Portfolio visibility and delegated payment authority are separate permissions. [S64][S64] [S99][S99] |
| slice · bank and UPI customers | Its activity centre lets users track spending. Current materials identify slice small finance bank. | A historical card applicant described a sanction letter followed by an unresolved activation problem and repetitive replies. | Keep application milestones and recovery routes distinct. Do not project a legacy card review onto current bank performance. [S65][S65] [S66][S66] [S100][S100] |

### Global analogues

| Company and segment | Documented journey | Customer feedback in the sample | Transferable lesson and limitation |
|---|---|---|---|
| Stripe · merchants accepting cards | Smart Disputes assembles and submits evidence for eligible disputes. | G2 reviewers value easy setup and integrations and raise fees and support responsiveness. | Evidence preparation is already competitive. Focus on hard-to-digitize local fulfilment records and a merchant’s right to concede. [S67][S67] [S101][S101] |
| Square / Block · independent sellers | Square links customer records across sales channels and segments eligible customers for marketing. | POS users praise setup and reporting and question cumulative fees. | Test one affordable, permissioned offer with a holdout. A payment identifier alone gives no marketing permission. [S68][S68] [S69][S69] [S102][S102] |
| Revolut · digital-bank users | Contextual scam interventions ask about a transfer’s purpose before it continues. | Reviewers praise ease of payments and report occasional verification or transfer delays. | Evaluate warning friction on legitimate payments alongside scam detection. Indian payment flows need local calibration. [S70][S70] [S103][S103] |
| Wise · cross-border senders | A transfer receipt lets a recipient’s bank trace a transfer after Wise marks dispatch complete. | Reviewers praise transfer speed and fee visibility and describe occasional verification holds or delays. | Give the next institution a traceable receipt. A partner’s dispatch event proves only its own step. [S71][S71] [S104][S104] |
| Monzo · UK banking customers | Trends estimates money left to spend after upcoming payments. | Users praise navigation and security prompts. The sample does not establish forecast accuracy. | Display covered obligations and uncertainty. A merchant with cash sales and supplier credit has a materially different data footprint. [S72][S72] [S105][S105] |
| Nubank · Brazilian banking customers | Street Mode lets users preconfigure transaction limits outside trusted Wi-Fi environments. | Reviews include ease-of-use praise and frustration supplying payment proof to support. No measured Street Mode satisfaction was found. | A user-selected protection can work alongside an explanation. Device context on its own is insufficient to classify fraud. [S73][S73] [S106][S106] |
| PayPal · buyers and sellers | A buyer and seller exchange evidence in the Resolution Center and may escalate an eligible dispute to a claim. | Reviewers like receipts and describe difficulty reaching a person during disputes. | Preserve shared case state and explicit escalation. PayPal purchase protection and UPI bank reversals have different rules. [S74][S74] [S107][S107] |
| Cash App · US families | Managed and sponsored accounts give parents age-specific oversight and controls. | Reviewers praise convenient transfers and report freezes or difficulty resolving disputes. Family-specific satisfaction was unverified. | Make delegated roles explicit. NPCI’s UPI Circle supplies the Indian authorization model. [S75][S75] [S37][S37] [S108][S108] |
| Klarna · shoppers and merchants | Reporting a return can pause a qualifying invoice while proof of return is retained. | Reviewers welcome payment flexibility and report difficulty with billing concerns or unexpected limits. | Reflect unresolved evidence in the case timeline. Only the lender or authorized biller can change an obligation. [S76][S76] [S109][S109] |
| Shopify · commerce merchants | Inventory reports connect recorded item sales, on-hand units and days of stock remaining. | Reviewers praise simple administration. An Indian seller objects to the combined cost of platform and gateway fees. | Offer an invoice-first path for small shops. QR receipts supply amounts but cannot identify the items sold. [S77][S77] [S110][S110] |
| Toast · US restaurants | xtraCHEF captures supplier invoices and connects ingredient costs with restaurant operations. | An operator case study praises invoice automation. G2 also records dissatisfaction with support. | Localize pack sizes and supplier aliases. Require recipe quantities before showing dish-level margin. [S78][S78] [S79][S79] [S111][S111] |
| Adyen · enterprises and multi-site merchants | The settlement details report attributes entries to batches and merchant accounts. | A reviewer praises transparent payment states but finds the dashboard difficult to interpret at a glance. | Preserve the accounting detail. Let a branch manager investigate one discrepancy without disclosing other branches. [S80][S80] [S112][S112] |


## Part 3. Fifteen evidenced customer and merchant problems

Ordered for this product decision. **Direct** means a person or study reports the experience. **Documented** means a provider or authority describes the failure condition or recovery work. These establish that a problem exists. The right-hand column identifies what a Paytm pilot would still need to measure.

| # | Friction and affected user | What the evidence establishes | Missing decision evidence |
|---|---|---|---|
| 1 | A shop owner cannot connect a bank credit to a day’s sales. | **Direct + documented.** A 28 October 2025 merchant review praises the old day-wise labels and describes manual calculation after a change. Paytm instructs users to match the bank reference. [S81][S81] [S10][S10] | Median minutes per close and how often better labels alone solve it. |
| 2 | Refunds, deductions and timing differences make gross takings look short. | **Documented.** Paytm records commissions, GST, refunds and net settlement separately. Merchant repayment can also come out of settlements under a loan arrangement. [S08][S08] [S18][S18] | Mix of legitimate netting, delayed credits and actual errors by merchant type. |
| 3 | Payer success and merchant failure create pressure to pay twice. | **Direct + documented.** A café customer describes ₹840 paid through GPay on a Paytm POS and a second card payment. NPCI separately defines missing online beneficiary confirmation. [S82][S82] [S25][S25] | Duplicate-payment incidence. A disagreement does not establish which record is correct. |
| 4 | A payer waits for a reversal and cannot identify the right clock or owner. | **Documented + direct.** RBI distinguishes failed UPI fund transfers from missing merchant confirmation. Google directs some users back to merchant or bank. A Google Play reviewer describes paying cash after a debit. [S26][S26] [S47][S47] [S83][S83] | Time spent outside the applicable resolution window by transaction type. |
| 5 | A support transfer makes the user repeat the evidence. | **Direct + institutional.** The café case involved the bank, merchant and a conference call. Mobile/electronic banking was the largest complaint category for non-bank payment system participants in RBI’s FY25 Ombudsman report. [S82][S82] [S27][S27] | Repeat contacts per incident at Paytm. The RBI category covers more than UPI. |
| 6 | A merchant must find the right proof before a chargeback deadline. | **Documented.** Paytm exposes a dispute lifecycle. Razorpay specifies evidence by reason. Pine Labs supports document upload from its merchant app. [S13][S13] [S55][S55] [S56][S56] | Fraction of eligible cases lost through missing evidence or late response. |
| 7 | A persuasive scam starts in another channel before the payment app opens. | **Survey + product evidence.** GSMA’s India survey reports messaging apps in 46% and voice in 32% of victims’ cited channels. Categories overlap. Paytm documents impersonation and payment-request precautions. [S42][S42] [S16][S16] | Precision on a consented, representative set of local messages and legitimate lookalikes. |
| 8 | A failed or duplicate-looking mandate leaves consumers unsure what will debit. | **Direct + documented.** A PhonePe user reported duplicate-looking mandates. A BHIM user reported a revoke error. Groww documents an active mandate with a missing instalment. [S88][S88] [S84][S84] [S59][S59] | Distinguish stale display, failed authorization and genuinely duplicated debits. |
| 9 | A restaurant’s ingredient cost changes before its menu or bundle price does. | **Direct.** Indian operators described reducing portions or changing menus in response to costs. A Toast restaurant customer describes the work of tracking invoice costs. [S45][S45] [S79][S79] | How many outlets have usable invoices, recipes and item counts. |
| 10 | Small suppliers can show strong sales while lacking cash for bills due this week. | **Industry study.** GAME/FISME/C2FO estimated ₹7.34 lakh crore in delayed MSME payments as of March 2024. This concerns trade receivables across MSMEs. It does not measure Paytm settlement delays. [S43][S43] | Receipt timing, cash sales and payable coverage for the proposed segment. |
| 11 | Borrowers face excessive documentation and difficulty comparing loan terms. | **Institutional + direct.** RBI identifies documentation and transparency barriers for MSMEs and requires comparable disclosures in applicable multi-lender digital journeys. A Navi user described difficulty understanding consequences after a missed payment. [S28][S28] [S30][S30] [S96][S96] | Whether a borrower can accurately explain total cost and a missed-payment scenario. |
| 12 | Device downtime persists after a merchant has already reported it. | **Direct + documented.** BharatPe and Pine Labs reviewers describe unresolved terminal faults. Paytm publishes Soundbox battery troubleshooting. [S92][S92] [S94][S94] [S17][S17] | Repair time, avoidable dispatches and confirmed restoration by device model. |
| 13 | Discounts and percentage fees can erode the margin on a restaurant visit. | **Industry testimony + inference.** NRAI warns of margin pressure from deep discounts and percentage fees. Incremental return visits obscured by redemption counts are a measurement hypothesis, not a surveyed complaint. [S44][S44] [S21][S21] | Net contribution versus a randomized holdout, including discount cost. |
| 14 | Households need delegated spending while retaining control over access. | **Direct + documented.** A student asked about paying hostel bills using a parent’s PhonePe account through UPI Circle. NPCI identifies secondary users who depend on a primary account holder. [S85][S85] [S37][S37] | Which households need additional help after onboarding and whether voice prompts suffice. |
| 15 | Text-heavy financial instructions exclude some users at the point of recovery. | **Research + operating precedent.** NPCI’s conversational payments paper discusses language and accessibility barriers. BCG’s merchant research records the value of audible confirmation and delegated counter work. [S41][S41] [S40][S40] | Comprehension in each language, code-switching and noisy shops, especially for amounts and dates. |

**Two signals worth keeping in proportion.** NPCI’s August 2025 table lists SBI remitter technical declines at 0.42% and business declines at 5.92%, on 5,368.74 million transactions. Those figures are specific to one bank and month. Combining the two as addressable support failures would materially inflate the opportunity. A merchant’s request for clearer dates also suggests a cheap baseline for Hisab Saathi: improve the date labels and add a UTR lookup before testing the agent’s incremental benefit. [S25][S25] [S81][S81]

## Part 4. Fifteen competitor innovations worth adapting

| # | Observed innovation | Paytm adaptation and the condition that makes it credible |
|---|---|---|
| 1 | Razorpay Recon matches multiple record types. [S53][S53] | Start an investigation when the match is missing. Preserve merchant-supplied proof and give the exception a service owner. |
| 2 | Adyen records transactions at settlement-batch and merchant-account level. [S80][S80] | Give each branch a gross-to-net explanation and restrict the owner’s consolidated view by role. |
| 3 | Wise issues a traceable receipt after sending funds to the receiving bank. [S71][S71] | Attach the appropriate UPI transaction reference or settlement UTR to the next party’s case. Label dispatch and receipt separately. |
| 4 | PayPal lets a dispute retain its history through escalation. [S74][S74] | Let the consumer and merchant contribute separately authorized records. Redact the opposite party’s bank details. |
| 5 | Stripe gathers evidence matched to an eligible dispute. [S67][S67] | Extract proof from local-language delivery documents and show the merchant which evidence is missing or contradictory. |
| 6 | Klarna links a reported return to the invoice state. [S76][S76] | Link order, refund initiation and bank credit as distinct events. Request a biller review only when that provider supports it. |
| 7 | Revolut asks context-specific questions during suspected scam payments. [S70][S70] | Let users voluntarily share the message that prompted a transfer. Explain one verifiable warning sign in their language. |
| 8 | Nubank lets a customer define a contextual security limit. [S73][S73] | Offer a user-selected verification step on unfamiliar payments. Validate accessibility and false alarms before testing enforcement. |
| 9 | CRED Protect extracts fee and EMI information from bills. [S50][S50] | Highlight a recurring debit that conflicts with the biller’s receipt, show its source and let the user correct the mapping. |
| 10 | Monzo estimates money remaining after scheduled obligations. [S72][S72] | Show a shopkeeper separate cash scenarios for an on-time and a delayed customer invoice. Mark omitted cash flows. |
| 11 | Toast digitizes invoices for food-cost analysis. [S78][S78] | Read a supplier bill, ask whether a pack size changed, and show the effect on a named dish using its recipe. |
| 12 | Shopify connects sales velocity to remaining stock. [S77][S77] | Warn about a fast seller only after the merchant supplies item-level records. Start with three menu items or SKUs. |
| 13 | Square groups customers for permissioned campaigns. [S68][S68] [S69][S69] | Test one merchant-approved offer with a randomized holdout and explicit budget. Show incremental contribution with uncertainty. |
| 14 | PhonePe provides multilingual spoken confirmation at the counter. [S46][S46] | Give a merchant a short spoken explanation of a reconciled amount and a private screen to inspect evidence. Paytm already has voice hardware. [S05][S05] |
| 15 | Cash App separates sponsor and spender controls. INDmoney separates family sharing from individual records. [S75][S75] [S64][S64] | Make the requesting person, approving person, data visibility and revocation route explicit in an existing UPI Circle journey. [S23][S23] |

**What fell outside the ten.** Generic spending categorization, a family payment dashboard and basic bill reminders are already served by Paytm or the network. International QR payments exist at selected overseas merchants. A Wise-style cross-border trace is attractive, but access to the overseas acquirer, currency conversion details and actual refund status makes it a weaker 48-hour build. Generic onboarding OCR also has a high overlap with Paytm’s existing AI-led merchant checks. The credit opportunity below starts after an actual document or offer exists. [S06][S06] [S23][S23] [S24][S24] [S38][S38] [S07][S07]


## Part 5. Ten product opportunities

**Shared prototype architecture.** Each concept below uses a mobile-first React interface, a FastAPI service, and SQLite for the demo. In production, use a tenant-scoped relational store, encrypted object storage for time-limited evidence, authenticated connectors and a durable job queue. A typed state machine records the inputs, tool result, policy version, approval and next allowed transition. The model receives minimized records and returns schema-validated fields with source IDs. The service validates dates, currency, permissions and allowed actions. Trace each tool call, latency, model version and handoff reason with masked identifiers. Every mutation has an idempotency key and an audit event. Each entry specifies the data, model, connector, failure mode and metric that distinguish it.

### 1. Hisab Saathi · merchant settlement investigation

**Problem and customer.** A kirana owner or small chain sees a bank credit below expected collections. The merchant can see the UTR and download reports, yet still has to map transaction days, batches, refunds and deductions. A merchant’s account of manual calculations and Paytm’s own two-source support procedure directly support this workflow. Razorpay Recon and Adyen are strong comparators. The proposed enhancement is a case that stays with the shop until its exception is accounted for. [S81][S81] [S11][S11] [S08][S08] [S53][S53] [S80][S80]

**Experience and AI.** The owner taps “Explain this deposit,” chooses a store and supplies a statement extract. A bilingual assistant interprets the question, identifies date or column ambiguities and asks for confirmation. The ledger service matches strong references and computes net amounts in paise. The screen separates verified credits, documented deductions, future-due batches and overdue unmatched amounts. The agent attaches evidence to a draft support case, gets approval to share it, rechecks on an event and closes only on verified receipt or authorized human disposition.

**Build in 24–48 hours.** Use a two-store ledger, two statement layouts, one approved refund and a simulated payout service. Implement statement import, ledger lookup, deterministic matching, a CRM ticket and an event consumer. One structured-output LLM maps unfamiliar headers and writes source-linked explanations. At 24 hours ship typed English, one layout and the case path. At 48 add Hindi, duplicate-callback recovery and a redacted evidence export. Exclude live banking and money movement. Paytm labels its Settlement API production-only. Missing reference, stale data or conflicting candidates must keep the case open. [S09][S09]

**Business test.** Compare assisted handling minutes, reopened cases and merchant comprehension against clearer date labels plus UTR search. First buyer is merchant support. An optional paid multi-outlet close could follow demonstrated retention or accounting time savings. No incremental payment revenue is assumed.

### 2. Payment Relay · consumer and merchant case handoff

**Problem and customer.** A payer shows “successful,” a cashier sees “failed,” and support receives conflicting narratives. The ₹840 café case includes a second payment and repeated handoffs. Google’s help flow directs users to different parties according to state. Paytm already accepts and tracks UPI complaints. NPCI’s HELP pilot and the reported MyUPI enhancement cover status and complaints, including eligible chargeback processing. This leaves a narrower opportunity in consented merchant-side corroboration and the second tender. [S82][S82] [S47][S47] [S14][S14] [S15][S15] [S34][S34] [S35][S35]

**Experience and AI.** The payer selects a transaction and optionally adds proof of the second payment. The merchant gets a time-limited link to confirm the order reference and share just its status. A model extracts references from receipts, detects contradictory statements and drafts a neutral timeline. A rules engine selects the appropriate rail and owner. When the bank or merchant responds, both parties see the status they are entitled to see. A missing response leaves a follow-up assigned to support. Wise’s trace receipt and PayPal’s shared case history are the precedents. [S71][S71] [S74][S74]

**Build in 24–48 hours.** Two role-scoped screens, mock PSP and merchant POS events, a card receipt fixture, versioned resolution rules, case API and asynchronous callback. Demo a payer screenshot conflicting with the merchant POS, then an issuer callback. Exclude cross-provider lookups without consent, real chargebacks and automatic reimbursement. Unknown rail or mismatched references go to an operator. Verify link expiry and measure contradictory records wrongly declared resolved.

**Business test.** Measure repeated explanations, second contacts and time until an accountable owner accepts the case. Potential value comes from lower support effort and recovered trust. A pilot needs both payer and merchant participation, which limits addressable cases.

### 3. Margin Diary · restaurant invoice-to-menu decisions

**Problem and customer.** A café can sell more of a popular combo while earning less on each sale after its supplier changes prices or pack sizes. Indian operators describe ingredient-driven menu changes. Toast shows that invoice capture and recipe costing can help restaurants. Paytm lists billing POS software. Paytm’s possible advantage is a lightweight workflow for a restaurant that already accepts its payments but still works from supplier bills. [S45][S45] [S78][S78] [S79][S79] [S20][S20]

**Experience and AI.** The owner photographs this week’s bill. A vision-language model proposes ingredient, quantity, unit and price with a highlighted source region. The owner confirms whether a “box” contains six or twelve packs. Deterministic unit conversion and a saved recipe calculate cost per serving. The owner sees which dish changed most, tries a supplier or price scenario, and saves a purchasing decision. Sales volumes come from itemized POS records or manual counts. A QR amount cannot identify a dish.

**Build in 24–48 hours.** Capture two synthetic supplier invoices, three recipes and one outlet’s item-sales CSV. A review screen writes confirmed aliases and pack conversions to the DB. Demo a stable invoice total hiding a smaller pack, then correct an OCR error. Exclude automatic orders, menu repricing, inventory optimization and full accounting. Use a printed bilingual fixture and flag handwriting or an unfamiliar unit for review. Track line-item extraction accuracy and cost-per-serving error after confirmation.

**Business test.** Test owner time to identify the changed ingredient and the gross contribution of the chosen action per serving. A merchant-software add-on is plausible if time saved and decisions changed justify the fee. Toast’s US success does not establish Indian willingness to pay.

### 4. Dispute Desk · chargeback evidence preparation

**Problem and customer.** A D2C seller or service provider receives a card dispute with a deadline. Proof is split across order records, delivery acknowledgements and customer messages. Paytm already has dispute IDs and responses, Pine Labs accepts uploads, and Stripe automates eligible evidence. The narrower job is finding missing or contradictory local fulfilment proof before a seller responds. [S13][S13] [S56][S56] [S67][S67] [S55][S55]

**Experience and AI.** Open the dispute, fetch the order and its delivery events, and display the deadline from the provider. Retrieval selects the evidence checklist for that reason code. OCR reads the supplied delivery slip. The model links each proposed claim to its document and highlights a mismatched date. The merchant can supply more proof, concede or approve an evidence packet. Only an authorized operator submits through the provider in production.

**Build in 24–48 hours.** Support one card reason code, a courier stub, shop-order API, two scanned proofs and a simulated dispute inbox. Demo one complete packet and one wrongly addressed receipt that blocks submission. Exclude scheme-wide coverage, invented evidence, legal advice and live filing. Redact addresses after field comparison. Alert on approaching deadlines and record reviewer changes.

**Business test.** Compare packet-preparation minutes, on-time responses and unsupported claims removed. Longer-term measure net merchant recovery after fees and effort, stratified by reason code. Optimizing win rate alone could encourage contesting valid complaints.

### 5. Scam Pause · explain a suspicious payment request

**Problem and customer.** A consumer, often helping someone or trying to collect a refund, may authorize a transfer after reading an off-platform message. GSMA finds that Indian scam exposure spans messaging, SMS and voice. Paytm already publishes protective guidance. Revolut uses contextual questioning and Nubank lets users preconfigure safeguards. The additional input here is the user-selected message and its relationship to the intended payment. [S42][S42] [S16][S16] [S70][S70] [S73][S73]

**Experience and AI.** A user shares a suspicious text or screenshot into Paytm before paying. A local-language model extracts the claimed purpose and any contradiction, such as being asked to send money to receive a refund. A deterministic policy renders an explanation, offers an independent verification route and records the user’s decision. Uncertain cases show what could not be checked. It never labels a payee safe from scant evidence.

**Build in 24–48 hours.** Use a share target or upload screen, OCR, a small bank-authored safety corpus and a mock payment-intent preview. Pair a fictional impersonation message with an almost identical legitimate invoice. Include Hindi and English, and let the user delete the attachment. Exclude background message or call access, live fraud blocking and PIN capture. If OCR or classification fails, show neutral verification steps. Log false reassurance and unnecessary prompts by language. [S16][S16] [S39][S39]

**Business test.** In consented simulations measure changes in user decisions, correct warnings and interruptions of legitimate transfers. Production depends on representative labels, red-team evaluation and a bank escalation route. Prevented losses and retention are unverified upside.

### 6. Loan Lens · borrower comprehension and application readiness

**Problem and customer.** For a first-time borrower or merchant, a simple application can still conceal a hard choice between fees, repayment cadence, term and total cost. RBI identifies documentation and transparency barriers and specifies disclosures for applicable digital offer comparisons. Paytm already distributes loans and publishes a ranking methodology. Navi demonstrates the direct digital-lender path, and BharatPe documents daily collections. [S28][S28] [S30][S30] [S29][S29] [S19][S19] [S58][S58] [S52][S52]

**Experience and AI.** The user opens two actual lender offers or uploads their Key Facts Statements (KFS). The agent extracts the lender-provided annual percentage rate (APR), fees, tenure and schedule with page references. The UI keeps each eligible offer visible. A deterministic calculator illustrates a low-sales week against the stated repayment contract. The borrower can ask for a plain-language explanation, correct an extraction, collect a missing document and choose whether to continue to the lender.

**Build in 24–48 hours.** Two fictional KFS PDFs, one missing fee, a document checklist and a lender handoff stub. Use OCR, structured extraction and a policy retriever. Demo a lower headline rate with higher total fees and an incomplete offer requiring clarification. Never estimate approval, rank by commission or create missing terms. Use lender-stated APR and flag inconsistencies. Keep unredacted documents out of traces. [S30][S30] [S29][S29]

**Business test.** Compare comprehension of total repayment, completion of eligible applications and clarification contacts. Production review belongs with the regulated lender and compliance team. A higher conversion rate is valuable only with comparable comprehension and fair presentation.

### 7. CounterCare · Soundbox and POS incident recovery

**Problem and customer.** A shop loses confidence in checkout confirmation when its device stops speaking or loses power. Merchants have reported delays after raising terminal faults. Paytm supplies troubleshooting and PhonePe demonstrates how much the customer journey depends on immediate spoken confirmation. [S92][S92] [S94][S94] [S17][S17] [S46][S46]

**Experience and AI.** The owner selects the affected device or reads its label. The teammate distinguishes a missing payment from a silent device by checking transaction status, heartbeat and last known settings separately. It asks one model-specific diagnostic question, offers a safe user action and tests whether confirmation has returned. If needed, it finds a service slot, asks the owner to confirm, and keeps the case open through the technician’s visit.

**Build in 24–48 hours.** A voice/text incident screen, two device manuals, synthetic telemetry, a mock slot inventory and a service-ticket tool. Demo a silent device with a successful payment, then a network outage with stale telemetry. Cache the last verified state, label its age and queue the ticket while offline. Exclude remote configuration changes, real field scheduling and reading sensitive amounts aloud by default. Verify one appointment per incident after retries.

**Business test.** Measure verified restoration, time without confirmation and unnecessary dispatches. Device subscriptions give Paytm a retention incentive. This is attractive if merchant interviews confirm repeat downtime and service operations can honor appointments. [S03][S03]

### 8. Mandate Map · resolve recurring-payment exceptions

**Problem and customer.** Subscription and SIP users can see an active mandate without knowing whether a particular bill was presented, paid or cancelled. PhonePe and BHIM users report failed revoke attempts. NPCI’s enhanced AutoPay framework provides for cross-app visibility and user-driven portability. Paytm offers reminders, CRED detects bills, and Google Pay documents native mandate controls. A consolidated list by itself is a weak opportunity. [S88][S88] [S84][S84] [S33][S33] [S24][S24] [S50][S50] [S48][S48]

**Experience and AI.** The user selects an unexpected debit. The agent links biller aliases, invoice period, mandate ID, debit attempt and receipt. It explains whether the records demonstrate an active authority, a presented bill or a settled debit. For uncertainty it asks for the biller reference. The user decides whether to open the native mandate-management flow or dispute a posted debit. The final screen waits for authoritative confirmation.

**Build in 24–48 hours.** Create synthetic mandate and biller events, one missed SIP and one cancelled subscription with a stale mandate view. A text model proposes possible biller aliases, while rules require exact identifiers for a confirmed link. Demo a revoke timeout and a read-only recheck. Exclude live cancellation, PIN handling and assumptions that revoking a mandate cancels the service contract. Measure false merges and verified terminal status.

**Business test.** Test fewer repeated support contacts around the same debit and better understanding of the next obligation. Existing native controls and incomplete third-party biller data limit uniqueness. [S59][S59] [S33][S33]

### 9. Cash Calendar · seven-day merchant liquidity scenarios

**Problem and customer.** A supplier, small chain or service business may owe wages and vendors before customers pay invoices. Industry evidence supports delayed trade payments. Monzo demonstrates future-obligation views for consumers, and Paytm documents loan deductions from merchant settlements. A sales chart omits both obligations and off-platform receipts. [S43][S43] [S72][S72] [S18][S18]

**Experience and AI.** The owner imports a receivables list, confirms the opening cash balance and photographs two payable invoices. OCR extracts due dates. The app displays scheduled obligations alongside alternative receipt dates and lets the owner correct cash takings. A simple historical model can estimate an interval when enough observations exist. The user chooses a reminder draft or a supplier conversation and sees its effect in the calendar.

**Build in 24–48 hours.** Seed two months of weekly patterns, an overdue invoice and a synthetic settlement feed. Build a baseline weekday median, error bands from held-out history where adequate, plus explicit on-time/late scenarios. With thin data show scenarios only. Demo the cash trough after a receipt slips three days. Exclude credit recommendations, automated collections and solvency claims. Mark every manual assumption and its age.

**Business test.** Measure forecast error against a naive weekly baseline and owner-reported surprises about obligations. Payment retention or a multi-location subscription is a hypothesis. The store may have substantial invisible cash or trade credit.

### 10. Repeat Visit Lab · test the profit from a merchant offer

**Problem and customer.** A salon or café can count coupon redemptions yet have little evidence that the offer paid for itself. NRAI cautions against margin erosion from deep discounts. Square supports customer groups, and Paytm already offers mLoyal, ROI tracking and retention analytics. The incremental opportunity is an affordable guided experiment with a margin floor. [S44][S44] [S68][S68] [S21][S21] [S22][S22]

**Experience and AI.** The owner states a goal such as filling quiet Tuesday hours, supplies available capacity and contribution per booking, and chooses an eligible opted-in audience. Rules enforce the margin floor and assign a holdout. A language model drafts local-language copy and explains uncertainty in the results. The owner approves budget, audience and copy before a test. Results include net contribution and a clear “too little evidence” state.

**Build in 24–48 hours.** Use mock booking and consent APIs, seeded anonymous customers, simulated redemptions and a campaign preview. Show an offer with many redemptions and negative incremental contribution. Refuse an audience with withdrawn permission. Exclude live outreach, inferred identities from UPI handles and any claim of measured lift from synthetic data. Freeze assignments to avoid double-enrollment.

**Business test.** Measure incremental contribution per eligible customer, opt-outs and merchant repeat use. Possible monetization is an add-on to merchant marketing. This ranks tenth because attribution needs time and sample size, Paytm already sells related tools, and cohort arithmetic requires little AI.


## Part 6. Opportunity ranking

Scores are weighted points awarded directly out of each column maximum. Severity measures consequence for the affected user. Market measures breadth and recurrence. Differentiation measures the proposed increment over public products. AI measures the useful work a model contributes beyond a rules-only baseline. Demo measures whether judges can observe a completed job. Build measures 48-hour feasibility. Business measures the plausibility of a Paytm buyer and measurable economic value. Data measures access to representative, permitted inputs. The scores are analyst judgments. They do not estimate market share, adoption or winning odds.

| Rank and product | Severity /15 | Market /15 | Difference /15 | AI /15 | Demo /15 | Build /10 | Business /10 | Data /5 | Total /100 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 Hisab Saathi | 15 | 14 | 11 | 13 | 15 | 10 | 10 | 5 | **93** |
| 2 Payment Relay | 15 | 15 | 11 | 13 | 15 | 9 | 9 | 4 | **91** |
| 3 Margin Diary | 13 | 13 | 12 | 14 | 15 | 9 | 8 | 4 | **88** |
| 4 Dispute Desk | 13 | 12 | 10 | 14 | 14 | 9 | 10 | 4 | **86** |
| 5 Scam Pause | 15 | 15 | 10 | 14 | 14 | 7 | 7 | 2 | **84** |
| 6 Loan Lens | 13 | 14 | 10 | 13 | 13 | 8 | 8 | 3 | **82** |
| 7 CounterCare | 12 | 13 | 11 | 10 | 14 | 9 | 9 | 3 | **81** |
| 8 Mandate Map | 12 | 14 | 9 | 10 | 13 | 9 | 8 | 4 | **79** |
| 9 Cash Calendar | 14 | 13 | 9 | 10 | 12 | 8 | 8 | 3 | **77** |
| 10 Repeat Visit Lab | 10 | 12 | 8 | 9 | 12 | 10 | 9 | 4 | **74** |

| Product | Principal user | Best-fit official track | AI contribution judges can inspect | 48-hour difficulty / main production dependency |
|---|---|---|---|---|
| Hisab Saathi | Shop owner and merchant support | Autonomous AI Teammates | Ambiguous statement mapping and a source-linked, bilingual discrepancy case | Low–medium / consented bank evidence |
| Payment Relay | Payer, cashier and dispute operator | Autonomous AI Teammates | Receipt alignment and contradictory evidence across two parties | Medium / scoped partner cooperation |
| Margin Diary | Restaurant owner or kitchen manager | Merchant Growth AI | Visual extraction and clarification of pack sizes | Medium / dependable recipes and itemized sales |
| Dispute Desk | Online seller and chargeback analyst | Autonomous AI Teammates | Reason-specific evidence retrieval and contradiction detection | Medium / authorized filing and fulfilment evidence |
| Scam Pause | UPI payer | AI-Powered Financial Journeys | Interpreting the intent behind a multilingual message | High / representative labelled cases |
| Loan Lens | Borrower and lender support | AI-Powered Financial Journeys | KFS extraction, grounded comparisons and comprehension checks | Medium / lender-reviewed documents and actions |
| CounterCare | Device merchant and field support | Autonomous AI Teammates | Interpreting symptoms across manuals, device state and payment logs | Medium / telemetry and dispatch integration |
| Mandate Map | Subscriber, bill payer or SIP investor | AI-Powered Financial Journeys | Biller-alias resolution across schedules and receipts | Medium / authoritative mandate and biller events |
| Cash Calendar | Small-business owner or branch manager | Merchant Growth AI | Payable extraction and uncertainty-aware receipt timing | Medium–high / off-platform cash and invoice coverage |
| Repeat Visit Lab | Salon or café owner | Merchant Growth AI | Translating a business goal into editable campaign terms and copy | Low for simulator / consent and time to measure lift |

**Product scope.** Hisab Saathi, Payment Relay, Dispute Desk, Scam Pause, Loan Lens, CounterCare and Mandate Map are enhancements to existing payments, distribution or support journeys. Margin Diary and Cash Calendar are adjacent merchant software products with separate adoption and pricing questions. Repeat Visit Lab is an experiment-design enhancement to merchant loyalty tools. These classifications are based on public materials, with internal product coverage unknown.

### Reasons for every score

Within each cell, reasons follow the order of the two displayed scores. The prototype data score gives credit for public schemas and realistic, testable fixtures. Access to live data is identified separately above.

| Product | Severity / market | Differentiation / AI | Demo / build | Business / data |
|---|---|---|---|---|
| Hisab Saathi | **15 / 14** · A shop doubts receipt of its takings. Many merchants settle repeatedly, but their exception rate is unknown. | **11 / 13** · Razorpay Recon is a close rival. Mixed evidence and language justify extraction and clarification, while exact matching stays in code. | **15 / 10** · A judge can trace every rupee and replay a late credit. A complete synthetic case needs only local services. | **10 / 5** · Support minutes have a clear owner. Public schemas and merchant-supplied statement layouts suffice for a representative prototype. |
| Payment Relay | **15 / 15** · Double payment directly hurts the payer. The journey spans the broad UPI merchant ecosystem. | **11 / 13** · MyUPI narrows status and complaint novelty. Identifying conflicting tenders across receipts is substantive model work. | **15 / 9** · Two screens make the disagreement visible. Consent scopes and callbacks add implementation work. | **9 / 4** · Fewer contacts are measurable. True cross-party outcomes require partner cooperation. |
| Margin Diary | **13 / 13** · A sustained cost change erodes earnings. The segment needs recipes or itemized sales. | **12 / 14** · Toast validates the category, with room for a lighter Indian workflow. Visual extraction and unit ambiguity are central. | **15 / 9** · A pack-size correction visibly changes dish margin. A small fixture set is practical. | **8 / 4** · Merchant software revenue is plausible but untested. Invoices are easy to simulate while real formats vary. |
| Dispute Desk | **13 / 12** · An incomplete response can cost a sale. Chargebacks concentrate among certain sellers. | **10 / 14** · Stripe already automates packets. Local fulfilment evidence still needs interpretation and grounding. | **14 / 9** · A blocked false submission is convincing. One reason code is straightforward. | **10 / 4** · Handling time and amounts at stake are tangible. Courier and merchant evidence are accessible by agreement. |
| Scam Pause | **15 / 15** · Authorized scams can create irreversible loss. Exposure crosses customer segments. | **10 / 14** · Guardrails exist in several apps. Understanding coercive context across languages benefits from AI. | **14 / 7** · Paired benign and suspicious examples are clear. Proving safe calibration in two days is difficult. | **7 / 2** · Trust matters, but attribution to one prompt is hard. Representative independently labelled cases are scarce. |
| Loan Lens | **13 / 14** · Misunderstanding borrowing costs has lasting effects. Credit journeys have broad relevance. | **10 / 13** · KFS disclosure and offer displays already exist. Reading varied terms and explaining them with provenance adds value. | **13 / 8** · An offer comparison and handoff are inspectable. Exact disclosures and repayment schedules need careful checking. | **8 / 3** · Better informed completion can help distribution. Lender templates and reviewed policy are needed to generalize. |
| CounterCare | **12 / 13** · Device failure disrupts checkout, though alternate verification may exist. Paytm has a large device footprint. | **11 / 10** · Confirmed restoration improves on a troubleshooting article. Many common diagnostics are simple rules. | **14 / 9** · A ticket, visit and restored signal form a clear ending. A simulator can cover a few failures quickly. | **9 / 3** · Dispatch cost and retention have owners. Actual telemetry and service capacity are private. |
| Mandate Map | **12 / 14** · Unexpected debits and missed instalments matter. Recurring payments span several use cases. | **9 / 10** · NPCI already enables substantial mandate management. Alias mapping helps, but authoritative status is deterministic. | **13 / 9** · A stale state and recovery can be shown live. A narrow event model is tractable. | **8 / 4** · Support contacts can be reduced. Native states are documented, while third-party biller context is uneven. |
| Cash Calendar | **14 / 13** · A missed supplier or wage payment is consequential. The useful segment must track obligations. | **9 / 10** · Cash planning is established. Document extraction helps more immediately than learned forecasts for thin histories. | **12 / 8** · A projected shortfall is understandable. Robust intervals and missing-data handling take time. | **8 / 3** · A treasury add-on may support retention. Missing cash takings can dominate model error. |
| Repeat Visit Lab | **10 / 12** · Wasteful discounts erode margin but owners can stop them. Relevant to merchants with repeatable visits. | **8 / 9** · Paytm already markets loyalty and cohort tools. Randomization and profit arithmetic do most of the work. | **12 / 10** · A simulated holdout is clear, although real lift takes weeks. The simulator is simple. | **9 / 4** · Campaign economics are measurable for a participating merchant. Real customer consent and adequate samples limit coverage. |

## Part 7. Top three recommendations

1. **Hisab Saathi for Autonomous AI Teammates.** The strongest demonstration is the moment a support operator learns that ₹600 of a gap has an ordinary explanation while ₹1,000 still requires investigation. Show the model reading messy evidence, deterministic code accounting for the money, and a later bank event changing the case. **Decision gate:** compare with a redesigned settlement statement on the same blinded cases. If clearer dates and UTR lookup solve almost everything, ship the UX fix and narrow the AI scope. [S81][S81] [S09][S09] [S53][S53]
2. **Payment Relay for a team with access to two-sided workflows.** The cashier and payer each have a valid reason to trust a different screen. The additional tender gives a judge an immediate reason to care. A consented handoff is its strongest feature. **Decision gate:** confirm both sides can share the minimal necessary proof and that the workflow adds something beyond Paytm complaints and MyUPI. Without merchant-side evidence it becomes a status viewer. [S82][S82] [S15][S15] [S35][S35]
3. **Margin Diary for Merchant Growth AI.** A supplier can hold the carton price steady while reducing the units inside. A photo, a pack-size clarification and a recalculated dish margin make the AI’s role unusually easy to inspect. **Decision gate:** ask restaurants for permission to test three actual invoice formats and two real recipes. If item or recipe data is unavailable, demonstrate purchase-cost variance and omit dish margin. [S45][S45] [S78][S78] [S20][S20]

**Sensitivity.** Hisab Saathi leads Payment Relay by two points. If a bank-statement import cannot be obtained even with merchant consent, cutting its data score from 5 to 2 moves it to 90. Payment Relay takes first place at 91 only if both sides of its case remain available. If the team must enter Merchant Growth AI, Margin Diary is the highest-ranked eligible concept at 88. These are decision scenarios, not confidence intervals.


## Part 8. Winning concept and 48-hour build brief

### Hisab Saathi — “Which sales reached my bank?”

**Product promise.** A shopkeeper can point to a deposit and see exactly which day’s sales it covers, which entries explain the difference and who owns the remaining investigation. The primary user is a merchant support operator working alongside the shop owner. A multi-outlet owner can scope the investigation to one outlet. The initial business model is lower cost per resolved support case. A paid multi-outlet close is a later pricing experiment.

**What the judge sees.** A mobile case, an operator queue and a visible evidence timeline. Each amount links to a source row. The agent can make read calls, request one clarification, draft a case, publish an approved ticket and recheck a delayed event. A user may switch between English and Hindi or use typed input in a noisy shop. Amounts remain visible as digits. The application announces only a generic status aloud unless the merchant opts into a private readout.

### Data contract and sample case

This example is synthetic. The ₹100 charge and settlement due times are values explicitly supplied by fixtures. They imply no standard Paytm tariff or timetable.

| Record | Fixture and authority | How it is used |
|---|---|---|
| Merchant scope and plan | Outlet A, authenticated owner, INR, Asia/Kolkata, plan version and cutoff | Derive due times from the applicable contract and business-day calendar. Enforce outlet access before reads. |
| Sales ledger | Yesterday’s captured sales total ₹20,000. Batch A has ₹19,000 and batch B has ₹1,000. Each order has an immutable ID. | Group by actual batch membership. Display sale day and deposit day separately. |
| Adjustments | Approved refund ₹500 and disclosed device charge ₹100, both in batch A, each with its own evidence ID | Compute A net ₹18,400 and B net ₹1,000. Expected net across both batches equals ₹19,400. |
| Settlement feed | Two payout references, batch IDs, status and timestamps. The fixture marks B past its plan-specific due time. | A processor’s dispatch event triggers a bank check. Preserve the source status and timestamp. |
| Merchant-provided bank extract | An original, permissioned statement slice covering the period shows ₹18,400 for A. A later statement update contains B’s ₹1,000 credit. | Match merchant scope, currency, reference and amount. The initial extract supports “no matching credit in this extract,” not proof of non-payment. |
| Service and approval | A reason code, redacted evidence bundle, CRM case ID, owner, next check, approval record and final disposition | Maintain one ticket per scoped exception. Append the late event, notify the operator and retain the audit trail. |

The opening difference from gross collections is ₹1,600. The refund and charge explain ₹600. The remaining ₹1,000 is unmatched in the first bank extract. The later credit brings confirmed bank receipts to ₹19,400. If the second credit arrives with a different reference, retain the unresolved state and ask for review. If the merchant has supplied only a partial statement, request the missing period before reporting an overdue, unmatched credit. [S08][S08] [S09][S09] [S10][S10]

### Agent architecture and workflow

| Component | Implementation choice | Verification and recovery |
|---|---|---|
| Intake | React mobile view for file/date selection, typed Hindi/English, optional push-to-talk with transcript confirmation | Redact account numbers before model calls. Ask the owner to confirm store, date range and any unclear amount. |
| Evidence interpreter | One structured-output multimodal model maps unfamiliar headers and proposes reference fields. Retrieve a versioned plan or FAQ using store/product scope. | Treat document instructions as content. Require row or page anchors and schema validation. Unknown signs, dates or columns require confirmation. |
| Reconciliation service | FastAPI with integer paise. Exact-reference and amount checks, aggregation by batch, explicit IST cutoff, adjustments deduplicated by source ID. | Amount-only matches never close a case. Route split credits, many-to-one ambiguity or contradictory sources to review unless a deterministic rule proves the match. |
| Workflow controller | Persist a state machine in SQLite for the demo. States include opened, awaiting evidence, investigating, awaiting approval, escalated, matched and human-disposed. Persist structured case memory and evidence versions. | Restart resumes from the last committed state. An outbox writes ticket intent in the same transaction as the transition. Retry transient failures with a stable idempotency key. |
| Tool boundaries | Read-only ledger lookup, settlement lookup and statement import. Separate tools for approved case creation, recheck and notification. A mock bank file and CRM are separate services or local HTTP endpoints. | Server checks merchant, store, role and purpose on every call. Confirm authorization before external sharing. No action grants the model bank credentials or a payout tool. |
| Operator handoff | Show facts, uncertainties, supporting rows, actions taken, owner and due time. Operator can correct mappings or record a disposition with a reason. | A new callback can update evidence. Deduplicate by event ID, reject stale sequence versions, and verify refreshed bank evidence before marking matched. |
| Monitoring | Structured spans for reads, mapping confidence, overrides, model cost, rule version, ledger invariants, ticket creation and terminal state | Dashboard counts unsupported closures, tool failures, aged exceptions, duplicate tickets and human review rate. Logs hold masked references, never raw statements. |

**API and test data.** Model the settlement connector on Paytm’s documented merchant-scoped API. It is production-only and its date query is constrained. Keep a labelled fixture adapter for the demo, with one-day slices, an empty response, and a separately uploaded bank statement. Include two shops with the same amount, a refund replay, a duplicate webhook, a missing UTR, a partial statement, a merchant-plan cutoff, an authorization denial and a CRM timeout after ticket creation. No access to Paytm, NPCI or a bank is required to run the prototype. [S09][S09]

**When conventional software wins.** With fixed statement headers and perfectly matched UTRs, the matcher and clearer labels already solve the case. The AI earns its place on unfamiliar bank layouts, local-language merchant explanations and contradictory unstructured proof. Measure its incremental benefit against templates and a rules-only importer. For routine files, bypass model inference. A single controlled agent is sufficient for the sprint.

### Delivery roadmap

| Elapsed time | Deliverable | Acceptance check |
|---|---|---|
| 0–4 h | Freeze one two-batch story, source schemas, state diagram, expected ledger results and one erroneous case. | A second person can account for every rupee using the fixture alone. |
| 4–12 h | Implement scoped local services, import, matching, cutoff handling and case persistence. | Exact match closes A. A same-amount record from another store cannot match B. |
| 12–20 h | Build merchant and operator views, anchored evidence cards and bilingual structured extraction for one statement layout. | An ambiguous column pauses for confirmation. Unsupported explanations cannot populate verified amounts. |
| 20–24 h | Add approval, ticket creation and a simulated late-credit event. Record the minimum complete demo. | One approved ticket, one confirmed close and a replayable trace survive reload. |
| 24–34 h | Add a second file layout, Hindi text review, partial import, contradictory entry, timeout and duplicate callbacks. | The case stays open on uncertainty and exactly one ticket survives an ambiguous CRM response. |
| 34–42 h | Run a blinded synthetic set, rules-only comparison, cross-store authorization and latency checks. | Report actual results and denominators, including failures. Label external services as simulated. |
| 42–48 h | Rehearse a three-minute demo, record a fallback video and prepare slides covering problem, technology, differentiation, impact and business model. | Demo works from a reset seed without external credentials. Use typed input if speech or network fails. |

**Live demonstration, three minutes.**

1. **0:00–0:30.** A shop owner asks, “Kal ₹20,000 ki sales thi. Bank mein ₹18,400 kyun aaye?” Show the selected outlet, sale date, bank date and scope of consent.
2. **0:30–1:05.** Import the statement. Show the model finding the bank-reference column in the second layout. Confirm its interpretation. Open the exact source row and show the independent integer calculation.
3. **1:05–1:35.** Display the ₹500 refund, ₹100 charge and ₹1,000 outstanding difference. Switch to the operator’s view. From the test console inject a same-amount credit for a different outlet. Show that the case stays open and the merchant never sees the other outlet’s data.
4. **1:35–2:15.** Approve sending only the masked references and discrepancy to support. The mock CRM times out after creating the case. The controller resumes with the same key and displays the existing ticket and next check.
5. **2:15–3:00.** Inject a bank update with the correct ₹1,000 credit and reference. The controller refreshes evidence, balances both batches and closes the ticket. Replay the event. Confirm one ticket, one closure and ₹19,400 in verified bank receipts. Let a judge inspect the audit trail.

### Measurement, economics and production gates

| Question | Proposed measurement and decision |
|---|---|
| Is the money right? | Sprint target: exact paise agreement on every labelled fixture and zero unsupported closures. Report correct matches / all proposed matches, matched eligible rows / all eligible rows, and abstentions. Include at least 20 independently labelled test cases spanning clean, ambiguous, overdue and partial inputs. Synthetic results establish implementation behavior only. |
| Does AI improve the workflow? | Randomize case order for operators using the agent versus clear date labels, deterministic matching and templated explanations. Compare time to verified resolution, field corrections, unsupported assertions and comprehension in each language. Keep source facts identical across conditions. |
| Does the workflow recover? | Repeat the ambiguous CRM timeout, duplicate callback and restart. Target one ticket and one final disposition per incident, no cross-merchant data exposure and a visible next action for every open case. |
| Will merchants use it? | In a consented pilot, measure eligible investigations started / eligible discrepancies shown, completion, reopen rates, and whether merchants agree with the final explanation. Segment by outlet size, bank-file format and language. |
| Does it pay for itself? | Monthly contribution hypothesis = eligible cases × adoption × net support minutes saved per assisted case × fully loaded cost per minute, less model, review, integration and operating costs. Compare net handling time including follow-ups. Measure merchant retention separately over a longer window. |
| What could stop rollout? | Unsupported bank formats, poor ASR for numbers, partial statements, changed plan rules and an already-equivalent internal product. Gate wider access on authorized data, exact matches, reviewed language quality and incremental value over the simpler baseline. |

**Production path.** Begin with five to ten consenting shop owners and a support team, using their existing redacted exports and timed manual closes. Next, shadow operator decisions on historical cases, maintaining a separate adjudicated set. Once the evidence and access controls hold, integrate a read-only approved merchant feed and an authorized CRM queue in one region. Introduce human-approved escalations, then narrowly defined automatic closures for independently verified exact matches. Expand to additional banks, languages and multi-store rollups only after measuring error for each. A bank-data connector requires a lawful and supported access route, explicit purpose, revocation and deletion or retention rules appropriate to the data. The DPDP rules have a phased timetable, and RBI’s payment-data storage direction has a defined regulated scope. Review applicability with Paytm and its regulated partners before selecting infrastructure or external model processing. [S31][S31] [S32][S32]

## Part 9. Sources and research limitations

**Method.** Reviewed Indian and global product documentation, Paytm disclosures, regulator and network publications, trade-body research, operator interviews, App Store and Google Play material, and public discussion. Used first-party sources for product behavior and reporting periods. Used field research and first-person evidence to test whether the described friction occurs. Global analogues contribute product patterns. They provide little evidence about Indian demand or comparative pricing. The scope is desk research through 8 November 2026.

**Limits that affect the decision.**

- No internal Paytm backlog, ticket volumes, bank telemetry, cohort retention, live product walkthroughs, underwriting data or merchant interviews were available. An apparent gap is a testable product hypothesis. A vendor may offer equivalent capabilities privately, for selected customers or in a newer build.
- An individual review establishes a reported experience. It cannot verify the underlying ledger, assign fault or establish prevalence. Store reviews are selected, sometimes old, and can describe a different part of the app. G2 and Trustpilot pages mix individual statements and platform summaries. Where positive or negative feedback for a particular feature was missing, no sentiment was inferred.
- NPCI circulars distinguish an announced framework from universal adoption by every PSP. The original HELP pilot is documented by NPCI. Two regulatory summaries describe September 2026 MyUPI changes. Availability in each app, and the exact current implementation for any one bank, were unverified. Do not pitch network status, mandate visibility or complaint filing as novel. [S34][S34] [S35][S35] [S36][S36]
- RBI’s failed-transaction circular describes UPI fund-transfer reversal by T+1 in the specified uncredited-beneficiary case and merchant-payment reversal within T+5 when the account was debited but confirmation did not reach the merchant. It specifies ₹100 per day beyond those respective limits. The scenarios and responsible institution must be established first. A return of goods, successful payment with a commercial dispute, and merchant batch settlement have different rules. Production needs a current, approved rule library. [S26][S26] [S13][S13]
- No real-world gains, model accuracy, merchant willingness to pay, national addressable case count, production API entitlement or judging preference were established. All product scores, sprint targets, fixture amounts, effort estimates and business impacts are proposals. Event dates are edition-specific. Close scores should be revisited after a merchant test.
- No historical FX rates, product pricing comparison or per-company satisfaction averages were used. Independent corroboration is strongest for settlement confusion, failed-payment handoffs, recurring-payment errors, MSME credit friction and restaurant costs. Device telemetry quality, family assistance demand beyond UPI Circle and causal loyalty lift remain materially less certain.

### Source register

Dates below refer to publication, the named reporting period or an identified review, as labelled. “Undated” means the reviewed material did not establish a publication date. All links were researched on 8 November 2026. Review feeds are dynamic.

#### Event briefs and Paytm product baseline

- **S01** · Event 13–14 Nov 2026 · [Hyderabad edition · organizer brief][S01]
- **S02** · Final 31 Oct 2026 · [Bengaluru edition · Paytm Community][S02]
- **S03** · 27 Oct 2026 · [Paytm · Q2 FY27 results][S03]
- **S04** · 7 Sep 2026 · [Paytm · authorized payment gateway plugin][S04]
- **S05** · 2025 announcement · [Paytm · AI Soundbox announcement][S05]
- **S06** · 25 Sep 2025 · [Paytm · spend summary and UPI statements][S06]
- **S07** · 22 Jul 2025 · [Paytm · AI-led merchant onboarding checks][S07]
- **S08** · Undated · [Paytm · settlement reports and deductions][S08]
- **S09** · Undated · [Paytm · Settlement API and production constraint][S09]
- **S10** · Undated · [Paytm · matching a settlement to a bank credit][S10]
- **S11** · Undated · [Paytm · missing settlement or payout][S11]
- **S12** · Undated · [Paytm for Business · Google Play product listing][S12]
- **S13** · Undated · [Paytm · chargeback lifecycle][S13]
- **S14** · 10 Jul 2026 · [Paytm · raising a UPI complaint][S14]
- **S15** · 10 Jul 2026 · [Paytm · tracking an existing complaint][S15]
- **S16** · Updated 26 Dec 2025 · [Paytm · scam precautions][S16]
- **S17** · Undated · [Paytm · Soundbox battery troubleshooting][S17]
- **S18** · Undated · [Paytm · merchant business loans and repayment][S18]
- **S19** · Undated · [Paytm · personal loan marketplace ranking logic][S19]
- **S20** · Undated · [Paytm · billing POS for retail][S20]
- **S21** · Undated · [Paytm · retention cohorts and merchant analytics][S21]
- **S22** · Undated · [Paytm · mLoyal omnichannel loyalty platform][S22]
- **S23** · Undated · [Paytm · UPI Circle delegation][S23]
- **S24** · 24 Dec 2025 · [Paytm · pending bill reminders][S24]

#### Regulation, payment infrastructure and sector research

- **S25** · Aug 2025 table · [NPCI · UPI remitter member and reversal statistics][S25]
- **S26** · 20 Sep 2019 · [RBI · failed transactions, reversal and compensation][S26]
- **S27** · 1 Dec 2025, FY2024–25 · [RBI · Ombudsman Scheme annual report][S27]
- **S28** · 29 May 2025 · [RBI · annual report, credit delivery and financial inclusion][S28]
- **S29** · 15 Apr 2024 · [RBI · Key Facts Statement for loans and advances][S29]
- **S30** · 8 May 2025 · [RBI · Digital Lending Directions][S30]
- **S31** · 14 Nov 2025 · [PIB · notification and implementation of DPDP Rules][S31]
- **S32** · Regarding directive of 6 Apr 2018 · [RBI · FAQ on storage of payment system data][S32]
- **S33** · 7 Oct 2025 · [NPCI · enhanced UPI AutoPay, OC 223][S33]
- **S34** · 8 Oct 2025 · [NPCI · UPI HELP Assistant pilot, OC 227][S34]
- **S35** · 13 Sep 2026 · [TeamLease RegTech · summary of MyUPI addendum][S35]
- **S36** · Circular dated 10 Sep 2026 · [Complinity · MyUPI addendum summary][S36]
- **S37** · Undated · [NPCI · UPI Circle][S37]
- **S38** · Undated · [NPCI · UPI Global Acceptance][S38]
- **S39** · Undated · [Union Bank of India · customer fraud-awareness guide][S39]
- **S40** · 2025 · [BCG / NPCI · UPI and the Indian merchant survey][S40]
- **S41** · 2024 · [NPCI partner paper · conversational payments on UPI][S41]
- **S42** · Oct 2025 · [GSMA · India Consumer Scam Report][S42]
- **S43** · Estimate as of Mar 2024, reported 2025 · [FISME · GAME/FISME/C2FO Delayed Payments Report 3.0][S43]
- **S44** · 8 Dec 2024 · [NRAI · advisory on dine-in discounts, hosted copy][S44]
- **S45** · 13 Oct 2026 · [Moneycontrol · interviews with Indian restaurant operators][S45]

#### Indian competitor products

- **S46** · Undated · [PhonePe · offline merchant solutions][S46]
- **S47** · Undated · [Google Pay India · merchant order and payment issues][S47]
- **S48** · Undated · [Google Pay India · managing AutoPay][S48]
- **S49** · 2026 · [Amazon India · Amazon Pay guide][S49]
- **S50** · Undated · [CRED · cards and CRED Protect][S50]
- **S51** · Undated · [BharatPe · merchant devices and facilitated loans][S51]
- **S52** · Undated · [BharatPe · lending and collection terms][S52]
- **S53** · 17 Dec 2024 · [Razorpay · Razorpay Recon launch][S53]
- **S54** · Undated · [Razorpay · settlement reconciliation API schema][S54]
- **S55** · Undated · [Razorpay · submitting reason-specific evidence][S55]
- **S56** · Undated · [Pine Labs One · merchant app and release history][S56]
- **S57** · Undated · [MobiKwik · LENS and bill payments][S57]
- **S58** · Undated · [Navi Finserv · digital lending application register][S58]
- **S59** · Undated · [Groww · active AutoPay with a missed SIP][S59]
- **S60** · Undated · [Jupiter · Spend Insights and Pots][S60]
- **S61** · 24 Apr 2024, updated 12 Sep 2025 · [Fi · Ask.Fi historical search experience][S61]
- **S62** · Fi partnership ended 31 Mar 2026 · [Federal Bank · status of fintech partnerships][S62]
- **S63** · Undated · [Fi · banking services update][S63]
- **S64** · Undated · [INDmoney · family accounts and sharing][S64]
- **S65** · Undated · [slice · UPI activity centre][S65]
- **S66** · Undated · [slice small finance bank · current product site][S66]

#### Global competitor products and operator testimony

- **S67** · Undated · [Stripe · Smart Disputes][S67]
- **S68** · Undated · [Square · Customer Directory][S68]
- **S69** · Undated · [Square · customer groups and marketing permissions][S69]
- **S70** · FY2025 · [Revolut · Consumer Security and Financial Crime Report][S70]
- **S71** · Undated · [Wise · recipient has not received a completed transfer][S71]
- **S72** · Undated · [Monzo · left-to-spend and estimated balance][S72]
- **S73** · 2 Feb 2024 · [Nubank · Street Mode use and trusted networks][S73]
- **S74** · Undated · [PayPal US · dispute-to-claim escalation][S74]
- **S75** · 2026 · [Cash App US · managed and sponsored accounts][S75]
- **S76** · Undated · [Klarna · return and invoice-pause workflow][S76]
- **S77** · Undated · [Shopify · inventory reports][S77]
- **S78** · Undated · [Toast · xtraCHEF invoice and cost management][S78]
- **S79** · Undated · [Toast · Underbelly Hospitality operator case study][S79]
- **S80** · Undated · [Adyen · settlement details report][S80]

#### Customer accounts and review platforms

- **S81** · Day-wise settlement review 28 Oct 2025 · [Paytm for Business · Indian App Store merchant reviews][S81]
- **S82** · 10 Feb 2025, incident 24 Dec 2024 · [Café customer · GPay success and Paytm POS failure][S82]
- **S83** · Undated · [Google Play · super.money payer review][S83]
- **S84** · 9 Feb 2026 · [BHIM user · unsuccessful mandate revocation][S84]
- **S85** · 4 Sep 2025 · [UPI Circle user · hostel expenses and parent account][S85]
- **S86** · 10 Mar 2026 thread · [Fi users · Federal Bank transition][S86]
- **S87** · Undated · [Jupiter · App Store interface review][S87]
- **S88** · Mixed review dates · [PhonePe · Indian App Store reviews][S88]
- **S89** · Mixed review dates · [GPay · Indian App Store reviews][S89]
- **S90** · Mixed review dates · [Amazon · Indian App Store reviews][S90]
- **S91** · Mixed review dates · [CRED · Indian App Store reviews][S91]
- **S92** · Mixed review dates · [BharatPe · Indian App Store reviews][S92]
- **S93** · Mixed review dates · [Razorpay · Indian App Store reviews][S93]
- **S94** · Mixed review dates · [Pine · Indian App Store reviews][S94]
- **S95** · Mixed review dates · [MobiKwik · Indian App Store reviews][S95]
- **S96** · Mixed review dates · [Navi · Indian App Store reviews][S96]
- **S97** · Mixed review dates · [Groww · Indian App Store reviews][S97]
- **S98** · Mixed review dates · [Jupiter · Indian App Store reviews][S98]
- **S99** · Mixed review dates · [INDmoney · Indian App Store reviews][S99]
- **S100** · Mixed review dates · [slice · Indian App Store reviews][S100]
- **S101** · Rolling review feed · [Stripe · G2 review evidence][S101]
- **S102** · Rolling review feed · [Square · G2 review evidence][S102]
- **S103** · Rolling review feed · [Revolut · Trustpilot review evidence][S103]
- **S104** · Rolling review feed · [Wise · Trustpilot review evidence][S104]
- **S105** · Rolling review feed · [Monzo · Trustpilot review evidence][S105]
- **S106** · Rolling review feed · [Nubank · Trustpilot review evidence][S106]
- **S107** · Rolling review feed · [PayPal · Trustpilot review evidence][S107]
- **S108** · Rolling review feed · [Cash App · Trustpilot review evidence][S108]
- **S109** · Rolling review feed · [Klarna · Trustpilot review evidence][S109]
- **S110** · Rolling review feed · [Shopify · G2 review evidence][S110]
- **S111** · Rolling review feed · [Toast · G2 review evidence][S111]
- **S112** · Rolling review feed · [Adyen · G2 review evidence][S112]

[S01]: <https://devsemble.com/hackathons/paytm-build-for-india-ai-hackathon-hyderabad-by-paytm>
[S02]: <https://luma.com/6afp5q46>
[S03]: <https://paytm.com/blog/investor-relations/paytm-q2-fy27-results-pat-225-crore-ebitda-rises-90-to-270-crore/>
[S04]: <https://paytm.com/blog/payment-gateway/paytm-payment-gateway-openai-chatgpt-plugin/>
[S05]: <https://paytm.com/document/ir/press-release/AI-SB.pdf>
[S06]: <https://paytm.com/document/ir/press-release/fy2025-26/sep/375236c4-12e8-44a1-a5b0-1c70290ba143.pdf>
[S07]: <https://paytm.com/document/ir/press-release/fy2025-26/jul/390a147e-db05-46a4-8195-fb46f7f420c0.pdf>
[S08]: <https://www.paytmpayments.com/docs/settlement-reports-on-dashboard>
[S09]: <https://www.paytmpayments.com/docs/api/settlement-api>
[S10]: <https://business.paytm.com/support/how-can-i-reconcile-payments-settled-to-my-bank-account>
[S11]: <https://business.paytm.com/support/i-didnt-receive-my-settlementpayout>
[S12]: <https://play.google.com/store/apps/details?hl=en_US&id=com.paytm.business>
[S13]: <https://www.paytmpayments.com/docs/disputes>
[S14]: <https://paytm.com/support/upi/how-to-raise-upi-complaint-paytm>
[S15]: <https://paytm.com/support/upi/track-upi-complaint-status-paytm>
[S16]: <https://paytm.com/support/using-the-paytm-app/avoid-scams-steps-to-secure-your-paytm-account>
[S17]: <https://business.paytm.com/support/what-should-i-do-if-the-my-soundbox-is-not-charging-and-has-battery-problems>
[S18]: <https://paytm.com/loans-credit-cards/business-loan/>
[S19]: <https://paytm.com/loans-credit-cards/assets/pdf/rbiDld2025Pl.pdf>
[S20]: <https://business.paytm.com/pos-billing-software>
[S21]: <https://business.paytm.com/support/what-is-the-use-of-analytical-tab>
[S22]: <https://business.paytm.com/paytmmloyal>
[S23]: <https://paytm.com/faqs/upi/how-does-upi-circle-work>
[S24]: <https://paytm.com/support/bill-payment/setting-up-reminders-for-pending-bill-payments-on-paytm>
[S25]: <https://www.npci.org.in/what-we-do/upi/upi-ecosystem-statistics>
[S26]: <https://www.rbi.org.in/commonman/Upload/English/Notification/PDFs/CIRCULAR677EC931A7A65E4D99AA957D8E85BC0A2A.PDF>
[S27]: <https://www.rbi.org.in/scripts/PublicationsView.aspx?id=23441>
[S28]: <https://www.rbi.org.in/scripts/AnnualReportPublications.aspx?Id=1434>
[S29]: <https://www.rbi.org.in/Scripts/NotificationUser.aspx?Id=12663&Mode=0>
[S30]: <https://www.rbi.org.in/Scripts/BS_ViewMasDirections.aspx?id=12848>
[S31]: <https://www.pib.gov.in/PressReleasePage.aspx?PRID=2190014&lang=2&reg=3>
[S32]: <https://rbi.org.in/CommonPerson/english/Scripts/FAQs.aspx?Id=2995>
[S33]: <https://www.npci.org.in/uploads/UPI_OC_No_223_FY_2025_26_Enhancement_of_UPI_Autopay_88b38535cb.pdf>
[S34]: <https://www.npci.org.in/uploads/UPI_OC_No_227_FY_2025_26_Introduction_of_UPI_HELP_Assistant_pilot_an_AI_powered_support_for_UPI_payments_cd501de8f3.pdf>
[S35]: <https://teamleaseregtech.com/updates/article/59466/npci-issued-addendum-to-upi-oc-227-yupi-al-powered-support-for-upi-pay/>
[S36]: <https://complinity.com/legal-update/npci-issues-addendum-to-upi-oc-227-myupi-ai-powered-support-for-upi-payments-upi-help-2-0--26124/>
[S37]: <https://www.npci.org.in/product/upi-circle>
[S38]: <https://www.npci.org.in/product/upi-global-acceptance>
[S39]: <https://www.unionbankofindia.bank.in/pdf/cyber_security_customer_awareness_guide_vol%20i.pdf>
[S40]: <https://web-assets.bcg.com/73/e5/e11f0db54da18a31a7cb55c1bef2/upi-the-global-benchmark-for-digital-payments.pdf>
[S41]: <https://www.npci.org.in/PDF/npci/knowledge-center/partner-whitepapers/Conversational-Payments-on-UPI-Unlocking-a-new-frontier-for-next-generation-payments.pdf>
[S42]: <https://www.gsma.com/about-us/regions/asia-pacific/wp-content/uploads/2025/10/GSMA-India-Consumer-Scam-Report-2025_FINAL_1010.pdf>
[S43]: <https://fisme.org.in/study/delayed-payments-to-msmes-decline-from-rs-10-lakh-cr-to-rs-7-lakh-cr-but-challenges-persist-game-fisme-report/>
[S44]: <https://www.medianama.com/wp-content/uploads/2024/12/NRAI-Advisory-on-Dine-in-8th-Dec-24.pdf>
[S45]: <https://www.moneycontrol.com/news/business/startup/smaller-portions-shorter-menus-25-higher-costs-restaurants-pass-rising-costs-to-consumers-14050779.html>
[S46]: <https://www.phonepe.com/business-solutions/offline-merchant/>
[S47]: <https://support.google.com/pay/india/answer/9494510/fix-issues-with-orders-or-payments-to-merchants?hl=en>
[S48]: <https://support.google.com/pay/india/answer/10452280>
[S49]: <https://www.aboutamazon.in/news/amazon-pay/amazon-pay-guide-wallet-upi-features>
[S50]: <https://cred.club/cards>
[S51]: <https://www.bharatpe.com/bharatpe-speaker>
[S52]: <https://www.bharatpemoney.com/documents/TERMS-AND-CONDITIONS-FOR-LENDING-SERVICES_FINAL-2-1.docx.pdf>
[S53]: <https://razorpay.com/newsroom/razorpay-pos-launches-industry-first-ai-powered-razorpay-recon-to-automate-reconciliation-for-businesses-boosting-financial-operations-efficiency-by-80/>
[S54]: <https://github.com/razorpay/markdown-docs/blob/master/api/settlements/fetch-recon.md>
[S55]: <https://tfs.np.razorpay.in/docs/payments/disputes/submit-evidence>
[S56]: <https://apps.apple.com/in/app/pine-labs-one/id6444654068?platform=ipad>
[S57]: <https://www.mobikwik.com/>
[S58]: <https://navi.com/finserv/lsp-dla/>
[S59]: <https://groww.in/help/mutual-funds/order/i-have-already-set-up-my-autopay-my-sip-didnt-get-deducted>
[S60]: <https://jupiter.money/>
[S61]: <https://fi.money/guides/tech-speak-at-Fi/ask-fi-search-tool>
[S62]: <https://www.federal.bank.in/fintech-partnerships>
[S63]: <https://fi.money/>
[S64]: <https://www.indmoney.com/networth/family-accounts>
[S65]: <https://help.slice.bank.in/support/solutions/articles/84000375753-slice-super-upi>
[S66]: <https://slice.bank.in/>
[S67]: <https://stripe.com/payments/dispute-management>
[S68]: <https://squareup.com/us/en/point-of-sale/features/customer-directory>
[S69]: <https://js.squareup.com/help/us/en/article/6245-manage-customer-groups-and-filters>
[S70]: <https://assets.revolut.com/pdf/Revolut_Consumer_Security_and_FinCrime_Report_compressed.pdf>
[S71]: <https://wise.com/help/articles/2977950/why-does-it-say-my-transfers-complete-when-the-money-hasnt-arrived-yet>
[S72]: <https://monzo.com/help/budgeting-overdrafts-savings/trends-left-to-spend-web>
[S73]: <https://international.nubank.com.br/pt-br/consumidores/recurso-de-seguranca-do-nubank-modo-rua-ultrapassa-15-milhao-de-usuarios-e-e-mais-popular-entre-adultos-de-25-a-44-anos/>
[S74]: <https://securepayments.paypal.com/us/cshelp/article/how-do-i-escalate-a-paypal-dispute-to-a-claim-help367>
[S75]: <https://cash.app/learn/getting-started/parental-controls-setup-and-safety>
[S76]: <https://www.klarna.com/international/enterprise/merchant-support/what-happens-when-a-customer-makes-a-return/>
[S77]: <https://help.shopify.com/en/manual/reports-and-analytics/shopify-reports/report-types/default-reports/inventory-reports>
[S78]: <https://pos.toasttab.com/products/xtrachef>
[S79]: <https://pos.toasttab.com/vi-us/customers/underbelly-hospitality>
[S80]: <https://docs.adyen.com/reporting/settlement-reconciliation/transaction-level/settlement-details-report>
[S81]: <https://apps.apple.com/in/app/paytm-for-business/id1351301966?platform=iphone&see-all=reviews>
[S82]: <https://www.reddit.com/r/CreditCardsIndia/comments/1imd4xd/struggling_with_failed_upi_transaction_reversal/>
[S83]: <https://play.google.com/store/apps/details?hl=en-IN&id=money.super.payments&listing=fkbanner2>
[S84]: <https://www.reddit.com/r/UPI/comments/1qzzkfs/bhim_upi_unable_to_delete_upi_lite_or_revoke/>
[S85]: <https://www.reddit.com/r/UPI/comments/1n7z3gh>
[S86]: <https://www.reddit.com/r/personalfinanceindia/comments/1rpzzym/fi_federal_bank_partnership_ending_is_fi_shutting/>
[S87]: <https://apps.apple.com/in/app/jupiter-cards-upi-banking/id1507748747?platform=watch>
[S88]: <https://apps.apple.com/in/app/phonepe-upi-payment-recharge/id1170055821?platform=iphone&see-all=reviews>
[S89]: <https://apps.apple.com/in/app/google-pay-upi-cards-loans/id1193357041?platform=iphone&see-all=reviews>
[S90]: <https://apps.apple.com/in/app/amazon-india-shop-pay-minitv/id1478350915?see-all=reviews>
[S91]: <https://apps.apple.com/in/app/cred-credit-cards-bills-upi/id1428580080?platform=iphone&see-all=reviews>
[S92]: <https://apps.apple.com/in/app/bharatpe-for-business/id1329385873?platform=watch&see-all=reviews>
[S93]: <https://apps.apple.com/in/app/razorpay-accept-payments-now/id1497250144?platform=iphone&see-all=reviews>
[S94]: <https://apps.apple.com/in/app/pine-labs-one/id6444654068?platform=watch&see-all=reviews>
[S95]: <https://apps.apple.com/in/app/mobikwik-loans-upi-wallet/id600002523?see-all=reviews>
[S96]: <https://apps.apple.com/in/app/navi-upi-payments-insurance/id1541152485?platform=iphone&see-all=reviews>
[S97]: <https://apps.apple.com/in/app/groww-stocks-mutual-fund-ipo/id1404871703?platform=watch&see-all=reviews>
[S98]: <https://apps.apple.com/in/app/jupiter-cards-upi-banking/id1507748747?platform=iphone&see-all=reviews>
[S99]: <https://apps.apple.com/in/app/indmoney-stocks-mutual-funds/id1450178837?platform=iphone&see-all=reviews>
[S100]: <https://apps.apple.com/in/app/slice-upi-credit-card-bank/id1123372237?platform=iphone&see-all=reviews>
[S101]: <https://www.g2.com/products/stripe-stripe-payments/reviews?page=4&qs=pros-and-cons>
[S102]: <https://www.g2.com/categories/retail-pos>
[S103]: <https://www.trustpilot.com/review/www.revolut.com>
[S104]: <https://www.trustpilot.com/review/wise.com>
[S105]: <https://www.trustpilot.com/review/www.monzo.com>
[S106]: <https://www.trustpilot.com/review/nubank.com.br>
[S107]: <https://www.trustpilot.com/review/www.paypal.com>
[S108]: <https://www.trustpilot.com/review/cash.app>
[S109]: <https://www.trustpilot.com/review/klarna.com>
[S110]: <https://www.g2.com/products/shopify/reviews?page=10&qs=pros-and-cons>
[S111]: <https://www.g2.com/products/toast/reviews?qs=pros-and-cons>
[S112]: <https://www.g2.com/products/adyen-payments/reviews?qs=pros-and-cons>
