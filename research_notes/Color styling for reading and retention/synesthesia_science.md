# Science of synesthesia: reading, color, and memory (grapheme-color and related forms), with implications for a text-styling tool

Method note: notes compiled 2026-11-14 from web search and page fetches. Where a primary paper could not be opened (paywall/403/cookie wall), the claim is cited to the best accessible source and flagged "(secondary)". Citation corrections found while researching: Bor et al. 2014 is in *Scientific Reports* (not *Neuropsychology*); the *Neuropsychologia* training paper is Rothen et al. 2018; Meier and Rothen 2009 is in *Neuropsychologia*; Simner et al. 2005 colour regularities is in *Cognitive Neuropsychology*; Rothen, Meier and Ward 2012 could not be retrieved directly (cited via later papers).

## 1. Prevalence overall and by type

### Takeaway
Best unbiased estimate across many variants is about 4.4% (Simner et al. 2006, n=1,690 tested, 162 variants); grapheme-color alone is roughly 1-2.4% depending on cut-off and whether letters, digits or both count. There is no strong female bias once self-referral is removed (older 6:1 ratios came from self-referred samples). Sequence-space and day-colour appear commoner than grapheme-color, but per-type numbers for OLP and lexical-gustatory were not verified here.

### Cited Findings
- Simner et al. (2006, *Perception* 35:1024-1033): 1,690 people tested individually with objective consistency testing, overall prevalence 4.4% across 162 variants, grapheme-color 2%, female:male 1.1:1 overall and 0.9:1 for grapheme-color — as summarized in [Simner and Carmichael 2015, PMC4566887](https://pmc.ncbi.nlm.nih.gov/articles/PMC4566887). A search summary of the 2006 abstract says coloured days is the most common variant and a ~1 in 23 overall figure (secondary; paper itself not opened) — [Simner 2006 record](https://pubmed.ncbi.nlm.nih.gov/17076063/) / [core.ac.uk copy](https://core.ac.uk/download/520511903.pdf).
- Simner and Carmichael (2015): 3,893 screened, 54 grapheme-color synaesthetes (1.39%; 33 F, 21 M), female:male prevalence 1.55% vs 1.19%, ratio 1.3:1, not significant; at the looser 1.43 cut-off 94 synaesthetes (2.42%). Earlier 5.5-6.2:1 female ratios (Baron-Cohen 1996; Rich 2005; Barnett 2008) came from self-referred samples — [PMC4566887](https://pmc.ncbi.nlm.nih.gov/articles/PMC4566887).
- Carmichael et al. (2015) validation of the Synesthesia Battery: n=2,847 (1,317 M, 1,530 F); 140 self-reported grapheme-color (4.9%), only 34 genuine (score <1) = 1.2%; 90 self-reporters failed ("malingerers"); with the looser <1.43 cut-off 69 (2.4%) matched long-term-retest base rate of 2%. Letters AND digits both coloured: 0.5% (cut-off <1) to 1.1% (<1.43). No genuine synaesthetes in the 52-90 age range — [Carmichael et al., PMC5047354](https://pmc.ncbi.nlm.nih.gov/articles/PMC5047354).
- Sequence-space prevalence estimates ~9-14% and grapheme-color ~2-4% per a Frontiers article summary (secondary; ranges vary by study and method) — [Frontiers 2013, fpsyg.2013.00776](https://www.frontiersin.org/articles/10.3389/fpsyg.2013.00776/full) (surfaced via search; not opened).
- Ward (2013) *Annual Review of Psychology* is cited as the main review; one encyclopedia entry gives "approximately 5%" for any type and ">75 types, not all objectively confirmed" — [MIT Open Encyclopedia of Cognitive Science](https://oecs.knowledgefutures.org/pub/rma3jjdk) (secondary; the review itself was not opened).
- Older, self-referral-based lower estimates (e.g., 1 in 2,000) are minimum estimates — [search summary of Simner 2006 context](https://core.ac.uk/download/520511903.pdf) (secondary).

### Inferences
- A designer should assume that roughly 1 in 50-100 users could have grapheme-color synesthesia and perhaps several percent some form of synesthesia, but also that many self-identified synesthetes will have partial, weaker, or only-digit/only-letter forms.

### Gaps
- Per-type prevalence for ordinal-linguistic personification and lexical-gustatory from Simner 2006 could not be retrieved (paper and PubMed abstract inaccessible). Do not quote numbers for these without checking the paper.
- Strength of evidence for the prevalence figures: strong for grapheme-color (large samples, two independent groups), moderate for overall 4.4% (single sample, n~1,690).

## 2. Consistency of color associations, individuality, and shared regularities

### Takeaway
Within a person, grapheme-color associations are highly consistent over years (the defining behavioural marker); across people they are mostly idiosyncratic, but there are modest population-level regularities (A often red; frequency/semantic/initial-letter effects that also appear when non-synaesthetes are forced to pick colours).

### Cited Findings
- Consistency is the hallmark test; the Eagleman Synesthesia Battery scores colour-distance across repeated picks in one ~10 min session — [search summary of Eagleman 2007 / Carmichael 2015](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC5047354/) (secondary).
- Long-term test-retest: a 2013 *Psychological Science* paper reported consistent matches even with test-retest intervals approaching 8 years, with no sign of decline over time (the search snippet did not name authors; plausibly Simner and Logie style longitudinal work — unverified) — [PMC3648671 figure page](https://pmc.ncbi.nlm.nih.gov/articles/PMC3648671/figure/F1).
- The original RGB cutoff of 1 is considered too conservative; Euclidean distance in CIELUV colour space discriminates best (Rothen et al. 2013) — [Carmichael et al.](https://pmc.ncbi.nlm.nih.gov/articles/PMC5047354). Genuine synaesthetes were more accurate on a speeded congruency task (84.4% vs 70.5%, d=1.03) than people who self-reported but failed consistency; RT difference not significant — same source.
- Associations are "highly specific and idiosyncratic" but with large-scale patterns, e.g. A often red; cultural artifacts (e.g., educational materials like coloured fridge magnets) may shape associations (Witthoft and Winawer 2006); traits also run in families — [MIT Open Encyclopedia](https://oecs.knowledgefutures.org/pub/rma3jjdk) (secondary).
- Simner et al. (2005, *Cognitive Neuropsychology* 22:1069-1085), "Non-random associations of graphemes to colours in synaesthetic and non-synaesthetic populations": non-synaesthetes forced to choose colours show similar biases; frequency of the colour term pairs with grapheme frequency (high-frequency letters get high-frequency colour terms, saturation effect); initial-letter priming (b->blue, y->yellow) — summarized in [Edinburgh lecture slides](https://www.inf.ed.ac.uk/teaching/courses/cnl/CNL_08_9_synaesthesia.pdf) and a [2021 paper citing it](https://pure.uva.nl/ws/files/67032846/1_s2.0_S1053810021001185_main.pdf) (secondary; paper not opened).
- Hubbard et al. (2005, *Neuron* 45:975-985) found large individual differences among six grapheme-color synesthetes, and suggested the group may be heterogeneous (strength of experience tracking V4 activation) — [PubMed abstract](https://pubmed.ncbi.nlm.nih.gov/15797557/).

### Inferences
- Because within-person mapping is stable for years but between-person mapping is idiosyncratic, any default palette will match only a small subset of letters for any given synesthete; calibration to the individual is required.
- Population regularities (A=red, B=blue, Y=yellow, etc.) are only useful as a weak prior or "starting suggestion", not as a standard.

### Gaps
- Exact A=red statistics (percent of synaesthetes) were not retrieved; the "A is red" claim is only from the encyclopedia entry.
- Heterogeneity across *types* of grapheme-color synesthete (associators vs projectors, Dixon et al. 2004) was not retrieved in this pass.

## 3. Interference from imposed or incongruent colours; any benefit of matching external colours

### Takeaway
Strong evidence that incongruent printed colours slow colour-naming in grapheme-color synesthetes (synesthetic Stroop) and that congruent colours/primes speed responses; the interference is automatic and cannot be consciously suppressed. Direct evidence on whether coloured *text* helps or hinders *reading* or memory for synesthetes (as opposed to colour-naming) was not found.

### Cited Findings
- Dixon et al. (2000, *Nature* 406:365): single case "C" named the colour of digits with 100% consistent pairings; digits automatically elicited photisms that interfered with colour-naming on incongruent trials — [search summary](https://es.scribd.com/document/83470384/Dixon-cabn) (secondary).
- Mattingley et al. (2001, *Nature* 410:580-582): 15 grapheme-color synaesthetes; synaesthetic experience could not be consciously suppressed even when detrimental to the task; brief masked presentation eliminated the effect; later work (Smilek et al. 2001) argued conscious identification is not necessary but concept activation is — [Nature](https://link.springer.com/article/10.1038/35069062) and search summary (secondary).
- Priming: synaesthetes name a real colour patch faster when it matches the colour induced by an achromatic letter; effect is attenuated under attentional load and depends on grapheme identity not form (ambiguous 5/S study, *Cortex* 2006) — [Macquarie abstract](https://researchers.mq.edu.au/en/publications/attentional-load-attenuates-synaesthetic-priming-effects-in-graph/), [Cortex 2006](https://dx.doi.org/10.1016/s0010-9452(08)70349-6) (secondary).
- van Leeuwen, Petersson and Hagoort (2010): 19 synaesthetes vs 19 controls; congruent primes gave a 79 ms RT benefit relative to incongruent and 69 ms relative to non-inducing primes; controls showed no RT effect — [PMC2919410](https://pmc.ncbi.nlm.nih.gov/articles/PMC2919410).
- Hubbard et al. (2005) summary: synaesthetic colour aided texture segregation (experiment 1) and reduced crowding (experiment 2) in some synaesthetes, i.e. potential performance benefit from the internal colour — [PubMed](https://pubmed.ncbi.nlm.nih.gov/15797557/), [press summary](https://sciencedaily.com/releases/2005/05/050528144241.htm). However a visual-search study found no difference between synaesthetes and controls when synaesthetic colours should help or hurt (colours "do not camouflage form") — [City repository](https://city-test.eprints-hosting.org/id/eprint/14911/1/Synaesthetic%20colours%20do%20not%20camouflage%20form%20in%20visual%20search..pdf) (secondary; abstract-level).
- Mechanism caveat: Stroop-like interference does not by itself show the colour is perceptual; it can occur at semantic/decisional levels — [search summary of reviews](https://www.sfu.ca/~kathleea/docs/2005%20-%20Hubbard%20&%20Rama%20-%20Neurocog%20Mechs%20of%20Syn%20copy.pdf) (secondary). Synaesthetic colour did not suppress real-colour BOLD in colour areas (van Leeuwen 2010, above).
- Coloured-text tools for synesthetes: I found no study testing coloured fonts/overlays as an aid or hindrance for reading in natural synesthetes. (Odgaard et al. 1999 and Ramachandran and Hubbard 2001 pop-out studies are well known but were not retrieved in verified form in this pass.)

### Inferences
- If a tool renders a letter in a colour different from the user's internal colour, the mismatch is expected (by analogy to the Stroop and priming effects) to cost some processing speed in colour-naming-type tasks; effect on fluent reading is unknown.
- If a tool renders letters in the user's own colours, expected effect is neutral-to-facilitative for tasks involving the colour dimension; no evidence for a reading-speed benefit.

### Gaps
- No study of the cost/benefit of displayed colour on text reading speed, comprehension, or memory for synesthetes; no study of synesthete preferences for coloured fonts; no systematic collection of experience reports about assistive tools (popular accounts exist but were not reviewed).
- Odgaard 1999 and Ramachandran and Hubbard 2001 findings were not verified.

## 4. Memory advantages

### Takeaway
Moderate, replicated evidence that grapheme-color synaesthetes outperform controls on episodic memory (meta-analytic d ~0.6), including for stimuli that do not induce colour, so the advantage appears general (colour/visual processing or associative ability) rather than limited to synaesthetically coloured material. Effects are heterogeneous across tasks and types; lexical-gustatory and sequence-space show weaker or null effects; synaesthetes do not have exceptional memory overall.

### Cited Findings
- Meta-analysis, Ward, Field and Chin (2019, *Memory* 27:1299-1312): episodic/long-term memory d-hat = 0.61 (medium), working memory d-hat = 0.36, digit span small, abstract-image memory (where synaesthesia is arguably irrelevant) showed larger effects; synaesthetes generally do not have exceptional memory — [search summary of author manuscript](https://sussex.figshare.com/articles/journal_contribution/A_meta-analysis_of_memory_ability_in_synaesthesia/23470676) (secondary; PDF returned 403).
- Rothen, Meier and Ward (2012) review: enhanced ventral-stream-related processing and colour association retention; effect-size ranges cited by Lunke and Meier 2020: auditory verbal d=0.33-1.07; visual verbal d=0.45-1.84; cued recall shape-colour/location-colour d=0.31-1.50; colour recognition d=1.09; shape-shape associations d=-0.27; complex black-and-white figures d=-0.27 to 0.98 — [Lunke and Meier 2020, PMC7044321](https://pmc.ncbi.nlm.nih.gov/articles/PMC7044321/).
- Yaro and Ward (2007, *QJEP*): enhanced memory for colour even where there is no synaesthetic induction; normal memory for a complex figure; not uniformly replicated (Pritchard et al. 2013) — [Bristol record](https://research-information.bris.ac.uk/en/publications/searching-for-shereshevskii-what-is-superior-about-the-memory-of-/) and a [review noting non-replication](https://www.frontiersin.org/articles/10.3389/fpsyg.2013.00762/pdf) (secondary).
- Rothen and Meier (2010, *Memory* 18:258-264): standardized memory test in a group of grapheme-color synaesthetes; "ordinary rather than extraordinary" advantage (abstract not retrieved) — [BORIS record](https://boris.unibe.ch/11730) (secondary).
- Ward, Hovard, Jones and Rothen (2013, *Frontiers in Psychology* 4:762): Exp. 1: 28 grapheme-color synaesthetes vs 35 controls, advantage across words, non-words, scenes and fractals (F(1,61)=15.32, p<.001); Exp. 2: 33 vs 38, scene advantage (p=.002) but word advantage not significant; advantage not specific to coloured/inducing stimuli (largest for achromatic fractals); lexical-gustatory (18 vs 18) showed no advantage (p=.18) — [Frontiers](https://www.frontiersin.org/articles/10.3389/fpsyg.2013.00762/full).
- Lunke and Meier (2020, *Scientific Reports* 10:3484): 76 synaesthetes vs 76 matched controls, retest after >=12 months (mean 16.6); only pure grapheme-color group showed persistent advantage (forgetting for colour d=-0.55, p=.051; words d=-0.57, p=.045; borderline), grapheme-colour+sound-colour music advantage did not persist, sequence-space null — [PMC7044321](https://pmc.ncbi.nlm.nih.gov/articles/PMC7044321/).
- Child data: Smees, Hughes, Carmichael and Simner (2019, *Phil Trans B*) — 10-year-old grapheme-color synaesthetes had higher vocabulary and rated their own reading higher; earlier small-sample findings were thin; self-evaluated, not an objective reading measure — [Napier record](https://www.napier.ac.uk/research-and-innovation/research-search/outputs/learning-in-colour-children-with-grapheme-colour-synaesthesia-show-cognitive-benefits-in), [Sussex copy](https://sussex.figshare.com/articles/journal_contribution/Learning_in_colour_children_with_grapheme-colour_synaesthesia_show_cognitive_benefits_in_vocabulary_and_self-evaluated_reading/23478896) (abstract-level; full text 403).
- Autobiographical memory: synaesthesia linked to more vivid/detailed memories and less fading of childhood memories — [Sussex record](https://sussex.figshare.com/articles/journal_contribution/Synaesthesia_is_linked_to_more_vivid_and_detailed_content_of_autobiographical_memories_and_less_fading_of_childhood_memories/23451710) (title-level only).
- Gross et al. (2011, *Perception*) — appeared in results ([BU PDF](https://www.bu.edu/neuropsychology/files/2015/02/Gross-synesthesia-Perception2011.pdf)) but not read; no claim made.

### Inferences
- Memory benefit seems tied to enhanced colour/visual associative processing in grapheme-color synesthetes rather than to the synesthetic colour acting as a mnemonic on specific material; so displaying a synesthete's own colours is not specifically supported as a memory aid.
- Because several studies are borderline (p~.05) and subgroups differ, treat the memory advantage as real but modest and not a design lever.

### Gaps
- No experiment found that directly tests memory for text displayed in congruent vs incongruent external colours vs plain text in synesthetes.
- Rothen et al. 2012 and Ward 2019 full texts not directly read; effect sizes taken from secondary descriptions.

## 5. Can non-synesthetes be trained? Effects on memory or reading

### Takeaway
Training reliably produces synesthetic-Stroop-style behavioural effects in non-synesthetes; phenomenology is reported by many participants in intensive protocols but is small-sample, self-report, fades, and has demand-characteristic risk; no verified evidence that trained associations improve reading or memory.

### Cited Findings
- Meier and Rothen (2009, *Neuropsychologia* 47:1208-1211): about 10 min/day for 7 days (~3,300 trials) produced a synesthetic Stroop effect but no conditioned synesthetic response; no colour experiences reported — [BORIS](https://boris.unibe.ch/34133) and [search summary](https://ouci.dntb.gov.ua/works/4NZaApO4) (secondary). Sample size not retrieved.
- Colizoli, Murre and Rouw (2012, *PLoS ONE* 7:e39799): non-synesthetes read a book (>49,000 words, abstract) printed with coloured letters; modified Stroop effect afterwards but no performance advantage on crowding; critics note weak self-report (mean ~2.5/5 in one summary), no control group, near-chance memory for pairs after six months, reported ~17 participants (secondary) — [UvA repository](https://dare.uva.nl/id/d4604e88-cb11-427f-ac92-83cc0aad6cf3), [Discover coverage (popular)](https://www.discovermagazine.com/mind/can-you-learn-to-be-synaesthetic).
- Bor et al. (2014, *Scientific Reports*): 33 recruited, 14 completed (mean age 19.35; selected for high visual imagery); 9 weeks, ~30 min x 4-5 tasks/day x 5 days; 13 letter-colour pairs. Colour-naming Stroop congruency effect up (partial eta^2=0.475, d=1.45 post vs pre, ~100 ms); synesthetic Stroop post-training d=0.90 (semantic pairs) to d=1.23 (non-semantic); consistency of trained letters fell below genuine-synesthete threshold (pre vs post d=1.47); 9/14 reported colour experiences, 3 borderline, 2 none; 3-month follow-up: much phenomenology faded but Stroop effect remained; IQ (Cattell Culture Fair) gain ~12.5 points vs control (n=9, no active control; d=1.21), which authors call provisional; skin-conductance result inconclusive; reading speed and memory outcomes not reported in the main text — [PMC4235407](https://pmc.ncbi.nlm.nih.gov/articles/PMC4235407/). The authors explicitly do not claim to have created genuine synaesthetes.
- Rothen et al. (2018, *Neuropsychologia*): experimental group n=18 plus active and passive controls; only trained group showed letter-specific consistency, Stroop effects, phenomenology, reduced TMS phosphene thresholds and enhanced VEP — summarized in [Schwartzman, Bor, Rothen and Seth 2019, PMC6834010](https://pmc.ncbi.nlm.nih.gov/articles/PMC6834010).
- Kusnir and Thut (2012): incidental learning via visual search gave behavioural effects without phenomenology; Cohen Kadosh et al. (2009): 4 highly suggestible participants under hypnosis showed congruency effects and some consistency, but Anderson et al. could not replicate key behavioural effects; review states results mixed and most induction studies did not elicit self-reported experience; whether trained synaesthesia brings memory or reading benefits is "a question for future studies" — [PMC6834010](https://pmc.ncbi.nlm.nih.gov/articles/PMC6834010).
- Review conclusion: most studies suggest synesthesia cannot be acquired (Rothen and Meier 2014), but more recent extensive-training studies suggest it may be possible — [MIT Open Encyclopedia](https://oecs.knowledgefutures.org/pub/rma3jjdk) (secondary).
- Rothen et al. 2016 on trained associations and memory: not located. A Leiden thesis proposes (does not test) synesthetic association training for dyslexia fluency — [Leiden thesis](https://theses.liacs.nl/pdf/2016-2017-HenneveldR.pdf) (proposal only).

### Inferences
- Because trained colour-letter associations have been shown to produce Stroop-type effects and are acquired with reading coloured text, a tool that systematically colours text could in principle build associations in a non-synesthete, but there is no evidence it would help reading or memory.
- For a user who already has natural grapheme-color synesthesia, imposed training-style colouring could conflict with existing mappings.

### Gaps
- No verified reading-speed or memory improvement attributable to acquired associations; Bor 2014 working-memory/long-term-memory data not in the main text I could access; Rothen 2016 not found; sample sizes for Meier and Rothen 2009, Colizoli 2012, Kusnir and Thut missing in retrieved text.

## 6. Congruent coloured text, assistive tools, experience reports

### Takeaway
Essentially unstudied as a tool question. Only indirect evidence (Stroop and priming costs/benefits for colour-naming) exists.

### Cited Findings
- See Section 3: congruent external colour speeds, incongruent slows, colour-naming/priming tasks (van Leeuwen et al. 2010, n=19+19; Mattingley et al. 2001, n=15) — [PMC2919410](https://pmc.ncbi.nlm.nih.gov/articles/PMC2919410), [Nature](https://link.springer.com/article/10.1038/35069062).
- Synesthetic colours may aid crowding/texture segregation in some synesthetes (n=6) — [PubMed](https://pubmed.ncbi.nlm.nih.gov/15797557/); but visual-search camouflage study found no effect — [City repository](https://city-test.eprints-hosting.org/id/eprint/14911/1/Synaesthetic%20colours%20do%20not%20camouflage%20form%20in%20visual%20search..pdf).
- Search for synesthete experience reports of coloured fonts or interference from mismatched colours returned no peer-reviewed sources.

### Inferences
- Individual differences (projector vs associator, strength) probably moderate any benefit or cost.

### Gaps
- No peer-reviewed study on coloured-text assistive tools for synesthetes; experience reports not found (popular sources not examined).

## 7. Associations with learning, reading, dyslexia, creativity, autism

### Takeaway
Associations exist but are mostly correlational, small, or self-selected; causal claims are weak. Strongest: autism co-occurrence (n=164 vs 97) and over-representation in art students; reading/dyslexia evidence is thin.

### Cited Findings
- Autism: Baron-Cohen et al. (2013, *Molecular Autism* 4:40): synaesthesia in 18.9% (31/164) of autistic adults vs 7.22% (7/97) controls, p<.05 (a conference abstract reported 5.7% for controls — discrepancy) — [Mol Autism PDF](https://link.springer.com/content/pdf/10.1186/2040-2392-4-40.pdf), [ScienceDaily (popular)](https://www.sciencedaily.com/releases/2013/11/131119193908.htm).
- Art/creativity: Rothen and Meier (2010, *Perception*): about 7% grapheme-color synaesthesia in 99 art students vs about 2% in 96 controls; direction of causation unclear — [search summary](https://journals.sagepub.com/doi/pdf/10.1068/p6680) (secondary). Ward et al. (2008, *BJP*): self-referred n=82 over-represented in artistic occupations but no broad creativity-test advantage (secondary).
- Reading/learning: child grapheme-color synaesthetes had higher vocabulary and rated their reading higher, with objective advantages not established (Smees et al. 2019) — [Napier](https://www.napier.ac.uk/research-and-innovation/research-search/outputs/learning-in-colour-children-with-grapheme-colour-synaesthesia-show-cognitive-benefits-in).
- Dyslexia: no peer-reviewed study found directly measuring prevalence or reading in dyslexic synaesthetes; only a thesis proposal and a forum-based blog anecdote — [Leiden thesis](https://theses.liacs.nl/pdf/2016-2017-HenneveldR.pdf), [blog (weak)](https://cognitionandevolution.blogspot.com/2013/12/reading-comprehension-and-synesthesia.html).
- Hyper-connectivity or cross-activation accounts (Hubbard et al. 2005) are used to explain both synaesthesia and autism links but are theory, not proof — [PubMed](https://pubmed.ncbi.nlm.nih.gov/15797557/).

### Inferences
- Do not market a tool as treating dyslexia or learning difficulty on synesthesia grounds.

### Gaps
- Dyslexia and synesthesia prevalence data not found; objective reading outcomes in synesthetes not found; effect sizes for autism overlap lack independent replication in these sources.

## Implications for a text-styling tool

### Takeaway
Evidence supports personalizing (not fixing) colour mappings for grapheme-color synesthetes and treating colour as non-essential for readability; it does not support claims of reading or memory gains from coloured text.

### Cited Findings (evidence-supported)
- Personalize colour to the individual; mappings are stable within person across years but idiosyncratic across people (strong evidence; [Carmichael et al.](https://pmc.ncbi.nlm.nih.gov/articles/PMC5047354), [Hubbard 2005](https://pubmed.ncbi.nlm.nih.gov/15797557/), [MIT Open Encyclopedia](https://oecs.knowledgefutures.org/pub/rma3jjdk)).
- Avoid imposing fixed/default letter colours on grapheme-color synesthetes: incongruent displayed colours slow colour-naming in Stroop tasks and can't be consciously suppressed (strong for the Stroop effect, small samples n=15-19 per study; [Mattingley 2001](https://link.springer.com/article/10.1038/35069062), [van Leeuwen 2010](https://pmc.ncbi.nlm.nih.gov/articles/PMC2919410)). Cost for natural reading: unstudied.
- Congruent displayed colours produced faster responses (~70-80 ms in a priming/naming task, n=19; [PMC2919410](https://pmc.ncbi.nlm.nih.gov/articles/PMC2919410)); matching the user's own colours is therefore at worst neutral for such tasks (moderate evidence, naming tasks only).
- Do not claim memory gains: the synesthete memory advantage (meta-analytic d~0.6 episodic) is not specific to synaesthetically coloured material (moderate, [Ward et al. 2013](https://www.frontiersin.org/articles/10.3389/fpsyg.2013.00762/full), [Lunke and Meier 2020](https://pmc.ncbi.nlm.nih.gov/articles/PMC7044321/)).
- Training non-synesthetes with coloured letters yields Stroop-like effects but unverified reading/memory benefits and fading phenomenology (weak-to-moderate, tiny samples; [Bor 2014](https://pmc.ncbi.nlm.nih.gov/articles/PMC4235407/), [Schwartzman et al. 2019](https://pmc.ncbi.nlm.nih.gov/articles/PMC6834010)).
- Not all self-identified synesthetes pass objective tests (about 64% of self-reported grapheme-color cases failed the battery in one sample; [Carmichael et al.](https://pmc.ncbi.nlm.nih.gov/articles/PMC5047354)), so offer calibration rather than assuming a mapping.

### Inferences (not directly supported by studies)
- Provide a user-editable palette with a calibration flow modeled on the Synesthesia Battery (pick colour per letter/digit, repeat to check consistency); offer regularity-based starting suggestions (A=red, etc.) clearly labelled as population tendencies only.
- Make colouring optional and toggleable per letter, per word, or globally; default to off for non-synesthetes and provide a plain-text mode to avoid distraction from mismatch.
- Keep sufficient contrast and accessibility: a synesthete's inner colour may be low-contrast on the page; offer a mode that leaves text black with coloured underlines/halos, as the research does not tell us whether colour on the glyph itself is necessary.
- Treat projector vs associator differences as plausible moderators; allow adjustable intensity.
- Run A/B user testing with the individual (reading speed, comprehension, subjective comfort) since no published evidence exists on this use case.

### Gaps
- No direct empirical evidence on coloured-text tools for synesthetes; all design implications beyond "personalize and avoid imposing fixed colours" are inference.
