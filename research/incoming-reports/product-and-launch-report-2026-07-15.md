# Incoming Report: Product Design and Launch

> Status: user-supplied, unverified research input
> Intake date: 2026-07-15
> Source: attachment supplied in the project conversation
> SHA-256: `632D843C5E6E2FB94C5CD584D17A2E1240D29CC7A260BF630B71E0702C25FF0A`
> Authority: none; recommendations and claims below are not project decisions

This file preserves the supplied report content for provenance, with line
endings and non-semantic trailing whitespace normalized for Markdown storage.
Its claims are reviewed in
[the comparative report review](../report-review-2026-07-15.md). The missing
bibliography and unverified claims must not be promoted into architecture,
policy, or public capability statements.

## Verbatim Supplied Text

~~~text
Your Next Opponent Is You için açık kaynak ürün tasarımı ve lansman raporu
Yönetici özeti
Your Next Opponent Is You, sıradan bir “kişisel chatbot” olarak değil, kullanıcının geçmiş düzeltmelerinden, kabullerinden, reddedişlerinden ve doğrulanmış sonuçlarından öğrenen bir kişisel controller/critic katmanı olarak konumlandırılmalıdır. En doğru ürün tezi şudur: sistem kullanıcının sesini taklit etmez; kullanıcının yargı modelini çıkarır, bunu kapsamlı ve sürümlü belleğe dönüştürür ve diğer AI coding agent’larını bu modelle yönlendirir, sınar ve gerektiğinde durdurur. Bu yaklaşım, projenin kendi araştırma bağlamındaki “kaynak-temelli kişisel çekirdek”, “sınırlı bilinçli çalışma alanı”, “capability ≠ authority” ve “sourced, scoped, testable, versioned, reversible, protected envelope” ilkeleriyle uyumludur.

Teknik olarak bu ürün, Generative Agents’ın gözlem-planlama-reflection döngüsünü, Reflexion’ın ağırlık güncellemeden dilsel geri beslemeyle öğrenmesini, MemGPT’nin katmanlı bağlam/bellek yönetimini, CoALA’nın modüler bilişsel mimari yaklaşımını ve Voyager’ın doğrulanabilir beceri kütüphanesi fikrini birleştiren bir agent governance sistemi olarak tasarlanmalıdır. Kişiselleştirme literatürü de, kullanıcı tercihlerini doğrudan tek bir global profile indirgemek yerine, çok turlu etkileşimden çıkarılan örtük tercihler ve bağlama-duyarlı user modeling yaklaşımının daha gerçekçi olduğunu gösteriyor.

En kritik tasarım kararı şudur: ham konuşma arşivi doğrudan “kalıcı politika” sayılmamalıdır. Onun yerine, her kayıttan yalnızca kanıtlanabilir sinyaller çıkarılmalıdır: açık onay, açık ret, açık düzeltme, tercih, guardrail, commit’e yansıyan kabul, test sonucu, sonradan geri alınma, kapsam ve geçerlilik süresi. Sonra bu sinyaller “policy candidate” ve “skill candidate” olarak karantinaya alınmalı; replay, holdout, karşı-örnek arama, shadow mode ve insan onayı olmadan kalıcı controller davranışına terfi etmemelidir. Bu şart, son iki yıldaki bellek-zehirleme ve tool hijacking saldırıları nedeniyle artık opsiyonel değil, temel güvenlik gereğidir.

Ürün, local-first varsayımıyla başlamalıdır: ham konuşmalar, secrets, PII, derived identity ve yüksek riskli memory kayıtları cihaz içinde veya müşteri sınırında kalmalı; dış sistemlere yalnızca gerekli, redacted, provenance’lı ve amaçla sınırlı özetler çıkmalıdır. Bu yaklaşım; GDPR’nin veri minimizasyonu, amaç sınırlaması, privacy by design/default, silme hakkı, veri taşınabilirliği, güvenlik tedbirleri ve kayıt tutma ilkeleriyle de uyumludur. Özellikle kişisel veri tanımı, özel nitelikli veri yasağı/istisnaları, işleme hukuka uygunluğu, silme hakkı, veri taşınabilirliği, işleme kayıtları, şifreleme/pseudonymisation ve ihlal bildirim yükümlülükleri bu ürünün temel compliance omurgasını oluşturur.

Açık kaynak lansmanda en doğru model, yazılım kamusal; zihin özel ilkesidir. Kamuya açılan şeyler: şemalar, adapter API’leri, sentetik fixture’lar, benchmark’lar, red-team senaryoları, replay/evaluation altyapısı ve denetim araçlarıdır. Kamuya açılmaması gereken şeyler: gerçek kullanıcı konuşmaları, çıkarılmış özdeşlik çekirdeği, ham bellek kayıtları, secrets ve üçüncü taraf kişisel verileridir. Projenin kendi araştırma protokolü de açıkça gerçek kişisel geçmiş ile türetilmiş zihnin özel, kontrollü ve kaldırılabilir kalmasını; araştırma çıktılarının ise source-ledger, contrary evidence ve açık sınırlılıklarla hazırlanmasını ister.


Ürün konumlandırması ve kullanıcılar
Ürünün en güçlü pazarlama cümlesi, teknik gerçekliği doğru yansıttığı için şu olmalıdır: “It doesn’t learn to talk like you. It learns to judge like you.” Çünkü araştırma yönü, kullanıcının kimliğini, değerlerini, düzeltmelerini, eylemlerini, hedeflerini ve doğrulanmış sonuçlarını öğrenen, süreklilik sağlayan ve daha sonra bunu benzer bağlamlarda kullanan bir sistem tarif ediyor; ancak aynı metin sentience pazarlamasını ve yetki taşmasını özellikle reddediyor.

Bu nedenle ürün kategorisi “personal AGI” ya da “memory chatbot” değil, personal controller for AI coding agents olmalıdır. CoALA, dil ajanları için modüler bellekler, yapılandırılmış eylem alanı ve karar akışı önerirken; MemGPT, bağlam sınırı aşımı için katmanlı bellek yönetimini; Reflexion, geçmiş başarısızlıklardan dilsel öz-eleştiriyle öğrenmeyi; Voyager ise doğrulanabilir ve yeniden kullanılabilir skill library yaklaşımını gösterir. Bunların bileşimi, bu ürünün “tek model daha” değil, çok-agentlı workflownun üst denetleyicisi olmasını destekler.

Hedef kullanıcı üç halkada okunmalıdır. İlk halka, yoğun biçimde AI coding agent kullanan bağımsız geliştirici ve küçük ekiplerdir; bunlar en çok “ben bunu her seferinde tekrar düzeltiyorum” acısını yaşar. İkinci halka, güvenlik, compliance ve tenant izolasyonu gibi güçlü guardrail’leri olan startup ve ürün ekipleridir; bunlar için controller, yalnızca tercih değil kanıt ve yetki standardı da taşır. Üçüncü halka, kurumsal/regulated ortamlardır; burada personal memory’den çok proje-scope’lu ve rol-scope’lu controller katmanı öne çıkar. NIST AI RMF’nin güvenilirlik, güvenlik, şeffaflık, privacy-enhanced ve hesap verebilirlik boyutları özellikle ikinci ve üçüncü halka için ürün gereksinimi hâline gelir.

Kullanıcı ihtiyaçları düzeyinde ürünün çözdüğü esas problem, uzun konuşma geçmişini sırf “arama” yapılacak bir arşiv olmaktan çıkarıp, operasyonel karara dönüşebilir, sürümlü, kapsamlı hafızaya çevirmektir. Kişiselleştirme literatürü bunu destekliyor: LaMP kişiselleştirmenin retrieval ve profile conditioning ile anlamlı fark yarattığını; P-RLHF ve CoPL bireysel tercihlerin global ortalamaya ezilmemesi gerektiğini; çok turlu etkileşim üzerinden kişisel tercih çıkarımı yapan çalışmalar ise örtük tercihlerin explicit prompt’tan daha önemli olduğunu gösteriyor. Aynı zamanda PrefEval ve RealPref benzeri benchmark’lar, uzun vadeli tercih takibinin mevcut sistemlerde hızla bozulduğunu gösterdiği için ürünün esas vaadi yalnızca “hatırlar” olmamalı; “doğru şeyi hatırlar, doğru yerde uygular, yanlış yerde uygulamaz” olmalıdır.

İsimlendirme seçenekleri
Varyant	Güçlü tarafı	Zayıf tarafı	Repo önerisi	CLI önerisi
Your Next Opponent Is You.	Güçlü manifesto; kullanıcıya doğrudan seslenir	Package/CLI için uzun	your-next-opponent-is-you	ynoiy
NextOpponent	Ürün adı olarak ölçeklenir; kısa ve akılda kalır	Manifesto etkisi daha düşük	next-opponent	nextop
Opponent	En kısa teknik kimlik	Fazla genel; marka ayrışması zayıf	opponent	opp

Pratik öneri: marka adı tam cümle kalsın, repo slug your-next-opponent-is-you, CLI ise kısa kalsın. Böylece manifesto korunur, geliştirici ergonomisi düşmez.

Tehdit modeli, gizlilik ve güven modeli
Bu ürünün saldırı yüzeyi, klasik chatbot’tan belirgin biçimde daha geniştir; çünkü sistem yalnızca yanıt üretmez, kalıcı bellek yazar, geçmişi geri çağırır, policy candidate üretir ve başka agent’ların eylemini etkiler. OWASP’nin 2025 LLM risk çerçevesi; prompt injection, sensitive information disclosure, data/model poisoning, excessive agency ve vector/embedding weaknesses’i temel riskler olarak öne çıkarıyor. NIST AI RMF de AI risklerinin geleneksel yazılım risklerinden ayrıştığını; verinin ve bağlamın zamanla değişmesinin, beklenmeyen drift ve trustworthiness bozulması doğurduğunu vurgular.

En kritik tehditler, ingestion sırasında güvenin yanlış kurulması ile başlar. İndirect prompt injection, uzak içerikteki gömülü talimatların modele sızmasıdır; OWASP buna karşı uzaktan gelen içeriğin ayrı işaretlenmesini, sanitize edilmesini, yapılandırılmış prompt ayrımı, least privilege ve high-risk aksiyonlarda human-in-the-loop önerir. MCP’nin resmi taşıma spesifikasyonu da özellikle Streamable HTTP üzerinden çalışan sunucularda origin doğrulaması, localhost binding ve authentication gereğini açıkça yazar; aksi hâlde DNS rebinding gibi saldırılarla yerel araçlara uzaktan erişim mümkün olur. Bu nedenle YNOIY’de reader ile actor ayrımı şarttır: untrusted content okuyan parça ile araç çağıran/parola gören/parça terfi ettiren parça aynı trust domain’de olmamalıdır.

Uzun dönemli bellek, başlı başına yeni bir saldırı yüzeyi oluşturur. MemoryGraft, MemMorph, Hidden in Memory ve MemGhost/MemGhost-benzeri çalışmalar; zararlı deneyim kayıtlarının semantik olarak “başarılı örnek” gibi belleğe eklenip sonraki oturumlarda yeniden çağrılarak kalıcı davranış sapması ve tool hijacking yaratabildiğini gösteriyor. Bu sonuç, YNOIY için iki tasarım sonucuna zorlar: (i) aidiyeti ve doğruluğu kanıtlanmamış hiçbir kayıt controller policy’si olamaz; (ii) retrieval sonucu çıkan her memory kaydı “trusted state” değil, “candidate evidence” olarak işlenmelidir. Bellek, kendi başına otorite olmamalıdır.

Gizlilik ve compliance omurgası GDPR’den türetilmelidir. GDPR’ye göre kişisel veri, tanımlanmış veya tanımlanabilir bir gerçek kişiye ilişkin her bilgidir; buna çevrimiçi belirteçler, konum, ekonomik/sosyal kimlik ve tercihler de dâhildir. Aynı metin pseudonymisation’ı ek bilgi olmadan kişiye bağlanamama olarak tanımlar; bu da YNOIY’de identity mapping tablosunun ayrı tutulması gerektiğini destekler. Ayrıca veri işleme ilkeleri amaç sınırlaması, veri minimizasyonu, doğruluk, saklama süresi sınırlaması, bütünlük/gizlilik ve hesap verebilirliktir; privacy by design/default açık bir yükümlülüktür. Silme hakkı, veri taşınabilirliği, elektronik işleme kayıtları ve güvenli işleme için pseudonymisation + encryption da doğrudan uygulanabilir hükümler sunar.

Bu nedenle önerilen privacy posture şudur: local-first by default, hosted by exception. Ham transcript, secrets, üçüncü taraf PII, derived identity core ve yüksek riskli episodic memory cihaz içinde veya müşteri denetimli sınırda kalmalı; dışarı yalnızca redacted, provenance’lı, scope’u belirli ve gerekçesi kayıtlı özetler gitmelidir. Processor/controller rolleri, retention policy, deletion propagation ve breach notification süreçleri mimarinin içine gömülmelidir; bunlar sonradan “hukuki ek” gibi eklenmemelidir. GDPR Madde 33’ün 72 saat kuralı ve Madde 35’in yüksek riskli işleme için DPIA yaklaşımı, hosted mod ve enterprise mod için doğrudan uygulanmalıdır.

Güven modeli
Güven modeli dört temel ayağa dayanmalıdır: provenance, confidence, versioning, rollback. NIST AI RMF, güvenilir AI sistemleri için accountable/transparent ve privacy-enhanced boyutlarını; proje bağlamı ise “sourced, scoped, testable, versioned, reversible” zarfını zorunlu kılıyor. Bu nedenle her kalıcı kayıt için “kim dedi?”, “hangi bağlamda dedi?”, “nasıl çıkarıldı?”, “hangi sonuç bunu destekliyor?”, “eski sürümü neydi?”, “geri almak mümkün mü?” sorularının cevaplanması gerekir.


Önerilen provenance alanları şunlardır: kaynak sistem, konuşma/oturum kimliği, rol, zaman damgası, quoted-vs-authored ayrımı, extraction method, supporting evidence, contradiction links, confidence score, supersedes/replaced_by zinciri ve tombstone/deletion alanı. Confidence tek başına model olasılığı olmamalı; kanıt kompoziti olmalıdır: explicitness, tekrar sayısı, bağımsız destek, commit/test doğrulaması, sonradan geri alınmama ve kapsam netliği. Versioning ise immutable event log + materialized current view şeklinde tasarlanmalıdır; rollback, policy promotion’ın doğal parçası olmalıdır, acil müdahale mekanizması değil. Bu alanlar, hem audit’i hem deletion propagation’ı mümkün kılar.

Örnek provenance kaydı
json
Kopyala
{
  "record_id": "prov_01J0YNOIY8K4M6",
  "kind": "provenance",
  "source_system": "chatgpt",
  "source_surface": "web_export",
  "conversation_id": "conv_1842",
  "turn_id": "turn_37",
  "speaker_role": "user",
  "authorship": "user_authored",
  "quoted_content": false,
  "timestamp": "2026-07-10T21:14:33Z",
  "project_scope": ["global", "repo:cerberus-app"],
  "sensitivity": {
    "pii": ["online_identifier"],
    "secret_like": false,
    "special_category": false
  },
  "extraction": {
    "method": "rule_based_plus_model",
    "schema_version": "0.3.0",
    "prompt_hash": "sha256:...",
    "review_required": true
  },
  "supporting_evidence": [
    {
      "type": "user_correction",
      "ref": "conv_1842#turn_37"
    },
    {
      "type": "test_result",
      "ref": "ci_run_9912"
    }
  ],
  "confidence": 0.91,
  "status": "active",
  "supersedes": null,
  "deleted_at": null
}
Bellek taksonomisi, ingest hattı ve sinyal çıkarımı
Bellek tasarımı, ham sohbet arşivini tek tip “memory” olarak ele almamalıdır. Generative Agents, MemoryBank, MemGPT ve CoALA birlikte okunduğunda; episodic, semantic, procedural ve reflection benzeri katmanların ayrıştırılması gerektiği görülür. NIST ve kişiselleştirme benchmark’ları da gösteriyor ki, uzun dönemli tercih takibi ile tek-seferlik görev bağlamı aynı veri yapısında tutulduğunda hem doğruluk hem güvenlik bozuluyor. Bu nedenle YNOIY için altı değil yedi katmanlı bir bellek sınıflaması uygundur: constitutional, project, scoped, preference, episodic, negative, skill.

Constitutional memory, nadiren değişen çekirdek ilkeleri tutar: capability≠authority, kanıt gereği, secrets commit edilmez, destructive aksiyonlarda onay gerekir, kullanıcı kararları sinyaldir. Project memory, belirli ürün veya organizasyon bağlamında geçerli mimari ve güvenlik invariant’larını saklar. Scoped memory, repo, path, dil, task türü veya takım bağlamına özel kuralları taşır. Preference memory, kullanıcıya özgü ama risk-düşük tercihleri barındırır; örneğin planın ne kadar ayrıntılı olacağı, çıktı biçimi, branch stratejisi. Episodic memory, belirli olayların zamanlı kayıtlarını tutar. Negative memory, reddedilmiş yaklaşımları, anti-pattern’leri ve failure mode’ları saklar. Skill memory ise başarıyla uygulanmış, doğrulanmış prosedürleri ve akışları tutar. Bu ayrım, “persona”yı metin üslubuna değil, karar ve operasyon modeline bağlar.

Önerilen bellek şeması
json
Kopyala
{
  "memory_id": "mem_scoped_01J0YNOJ7AF2W",
  "memory_type": "scoped_policy",
  "title": "Mock kanıt, müşteri-kritik akışı kapatmaz",
  "statement": "User-facing acceptance boundaries require real-path evidence.",
  "scope": {
    "workspace": "global",
    "project": "your-next-opponent-is-you",
    "repositories": ["repo:core"],
    "paths": ["src/controller/**"],
    "task_modes": ["implementation", "verification"],
    "risk_classes": ["RC2", "RC3"]
  },
  "source_basis": [
    "prov_01J0YNOIY8K4M6",
    "prov_01J0YNOJ0A2A3M"
  ],
  "support_count": 4,
  "contradictions": [],
  "confidence": 0.94,
  "valid_from": "2026-07-10T00:00:00Z",
  "valid_to": null,
  "supersedes": null,
  "status": "active",
  "review": {
    "last_verified_at": "2026-07-12T11:00:00Z",
    "next_review_due": "2026-10-01T00:00:00Z"
  }
}
İngestion hattı için birinci ilke, connector’ların güven katmanına göre sıralanması olmalıdır. Birinci sınıf connector’lar: resmi export ve kullanıcının açıkça verdiği transcript/package yükleri. İkinci sınıf connector’lar: IDE/event adapter’ları, Git hook/CI kayıtları, terminal komut geçmişi, test çıktıları. Üçüncü sınıf connector’lar: copy-paste, markdown memory dosyaları, chat share link’lerinden elde edilen serbest metin. En son ve en riskli grup DOM scraping veya provider davranışını taklit eden kırıgan bağlayıcılardır; bunlar MVP’ye alınmamalıdır. Bunun nedeni yalnızca bakım maliyeti değil, provenance zayıflığıdır. MCP’nin stdio ve Streamable HTTP tabanlı açık protokolü, IDE ve agent adapter’ları için iyi bir taşıma ilkesi sunar; ayrıca yerel stdio sunucuları local-first mod için çok uygundur.

ChatGPT/Claude/Copilot/IDE ekosisteminde pratik ingest stratejisi şu olmalıdır: sağlayıcıya özel “her şeyi içe çek” mantığı yerine normalleştirilmiş event şeması. Bu şema en azından şu olayları desteklemelidir: message.created, message.edited, tool.called, tool.result, file.opened, file.edited, git.diff, commit.created, test.started, test.finished, ci.result, user.feedback, policy.override, memory.deleted. VS Code üzerinde çalışan araştırma araçları, semantik edit olayları, insert/delete, focus shift, test komutları ve debugging-process evidence gibi olayların eklenti seviyesinden yakalanabileceğini gösteriyor; bu da sağlayıcı-specific transcript’ten daha güvenilir bir ikinci sinyal yaratır.

Redaction hattı, persistence’tan önce çalışmalıdır; retrieval’da değil. OWASP, remote content sanitization için dış kaynaklardan gelen yaygın enjeksiyon örüntülerinin temizlenmesini, documentation/comment sanitize edilmesini ve şüpheli encoding’lerin decoding sonrası incelenmesini öneriyor. GDPR Madde 32 de özellikle pseudonymisation ve encryption’ı teknik tedbir olarak sayıyor. Buna göre redaction hattı en az dört aşamalı olmalıdır: secret detection, PII detection, quoted-third-party detection, unsafe-instruction tainting. Redaction sonrası tam metin yerine gerektiğinde referans + salted hash + saklama politikası kullanmak daha doğrudur.

Sinyal çıkarımında temel ilke şudur: assistant cevabı bağlamdır; kullanıcı kararı sinyaldir. Açık onay, açık ret ve açık düzeltme yüksek değerli sinyallerdir. Daha güçlü kabul sinyali ise “öneri → commit/diff → test/CI → revert olmaması” zinciridir. AutoRule ve doğal dil geribildirimiyle hizalama çalışmaları, insan geri bildiriminin salt sıralama değil, eleştiri ve revizyon olarak da çok değerli olduğunu gösteriyor. Bu nedenle extractor, yalnızca “thumbs up/down” tarzı yüzeysel sinyallere bakmamalı; serbest metin düzeltmeleri ve alternatif önerileri de policy candidate kaynağı olarak işlemelidir.

Önerilen sinyal sınıfları şöyledir. Approval: “tamam”, “aynen”, “böyle olsun” gibi açık onay + sonradan çelişki olmaması. Rejection: açık reddediş, alternatif öneri, ya da önerinin geri alınması. Correction: mevcut önerinin/patch’in neden yanlış olduğunun söylenmesi ve yeni constraint eklenmesi. Acceptance: önerinin gerçekten iş akışına girmesi; commit, merge, test success, deploy veya sonradan tekrar kullanımla desteklenmesi. Operational evidence: komut, test, CI, runtime doğrulaması. Negative evidence: revert, incident, failing replay, user rollback. Her sinyal explicitlik, bağımsız doğrulama ve zaman yakınlığına göre skorlansın; modellerin tek başına ürettiği “done” beyanları en düşük seviyede kalsın.

Risk sınıfı ve kanıt matrisi
Risk sınıfı	Örnek değişiklik	Minimum kanıt
RC0	Salt README, kopya düzenleme, non-executable docs	E0: lint/format veya gözle inceleme
RC1	Test/refactor, düşük riskli local helper, new parser rule	E1: unit + diff review
RC2	Controller routing, memory extraction, retrieval ranking, policy display	E1 + E2: unit + integration + replay
RC3	Policy promotion, deletion propagation, secrets/PII handling, tool authorization, hosted sync	E1 + E2 + E3: integration + holdout + adversarial cases + independent verifier

Kanıt seviyeleri önerisi:

E0: sentetik/mock destek kanıtı
E1: unit/property test
E2: entegrasyon ve replay
E3: gerçek akış / bağımsız doğrulayıcı / manual witness
E4: üretim-benzeri kabul, rollback planı ve audit izi
Bu matrisin mantığı, MemoryAgentBench’in retrieval-test-time learning-selective forgetting boyutları ile NIST’in ölçme/yönetme zorunluluğunu birleştirir; yüksek riskli yolun yalnızca “doğru yanıt” değil, doğru hatırlama ve doğru unutmama sorunu olduğunu kabul eder.

Controller mimarisi ve güvenli kendini geliştirme
Controller mimarisi altı ana bileşenden oluşmalıdır: intent compiler, router, opponent/critic, policy engine, memory query service ve independent verifier. Intent compiler, kullanıcının isteğini görev tipine, risk sınıfına ve gerekli kanıt düzeyine çevirir. Router, hangi ajanların ve araçların kullanılacağını belirler. Opponent/critic, planın kullanıcının geçmiş düzeltmelerine göre nerede itiraz göreceğini tahmin eder. Policy engine, constitutional/project/scoped kuralları uygular. Memory query service, ilgili ve güven skoru yeterli kayıtları getirir. Independent verifier ise plan ve patch’in gerçekten kanıt standardını karşılayıp karşılamadığını ölçer. Bu ayrım, CoALA’nın modüler ajan tasarımına ve NIST’in actor separation tavsiyesine uygundur.

En kritik bileşen opponent’tır. Reflexion, modelin kendi geçmiş hatalarından dilsel yansıma ile fayda gördüğünü; Constitutional AI ve AutoRule ise kuralların ya insan ilkelerinden ya da geri bildirimden çıkarılıp daha sonra eleştiri/revizyon döngüsünde kullanılabileceğini gösteriyor. YNOIY’de opponent modülü şöyle çalışmalıdır: “Bu plan neden kabul edilir?” ve “Bu planın hangi varsayımına kullanıcı itiraz ederdi?” sorularını aynı anda sormak. Amaç kullanıcıyı taklit etmek değil; kullanıcı gibi itiraz edebilmek. Bu, marka vaadini teknik gerçekliğe çeviren bileşendir.

Policy candidate yaşam döngüsü açık ve yavaş olmalıdır. Doğru süreç: extractor, tekrar eden kullanıcı düzeltmelerini ve verify edilmiş sonuçları yeni bir aday kural veya skill olarak çıkarır; aday karantinaya girer; historical replay üzerinde denenir; holdout örneklerde baseline’a göre fayda ve zarar ölçülür; karşı-örnek araması yapılır; sonra shadow mode’da canlı trafiğe öneri üretir ama karar vermez; ancak eşik geçilirse insan onayıyla promote edilir. Proje bağlamındaki “autonomous promotion”, “replay”, “temporal holdout”, “canary”, “quarantine”, “rollback” ve “hard stop conditions” talepleri tam olarak bu yaşam döngüsünü gerektiriyor.

Örnek policy candidate kaydı
json
Kopyala
{
  "candidate_id": "pc_01J0YNOPZ6S2T",
  "kind": "policy_candidate",
  "title": "Gerçek kabul sınırında mock kanıt yeterli değildir",
  "proposed_rule": "Do not close user-facing acceptance boundaries with mock-only evidence.",
  "derived_from": [
    "prov_01J0YNOIY8K4M6",
    "prov_01J0YNOJ0A2A3M",
    "ci_run_9912"
  ],
  "scope": {
    "repositories": ["repo:core", "repo:cli"],
    "task_modes": ["verification", "implementation"],
    "risk_classes": ["RC2", "RC3"]
  },
  "support": {
    "explicit_user_corrections": 3,
    "accepted_after_revision": 2,
    "contradictions": 0
  },
  "evaluation": {
    "replay_pass_rate": 0.92,
    "holdout_gain": 0.11,
    "counterexamples_found": 1,
    "shadow_mode_precision": 0.88,
    "shadow_mode_false_block_rate": 0.04
  },
  "decision": {
    "status": "quarantined",
    "requires_human_promotion": true,
    "risk_level": "high"
  },
  "version": 1,
  "created_at": "2026-07-14T18:22:00Z"
}
Güvenli self-improvement için ana kural şudur: sistem kendini değiştirmez; değişiklik önerir. Reflexion ve Voyager, ağırlığı güncellemeden ya da devasa yeniden eğitim olmadan davranış düzeyinde iyileşmenin mümkün olduğunu gösterir; ama yakın dönem memory poisoning çalışmaları, bu kabiliyetin kötüye de kullanılabileceğini ortaya koyuyor. Bu yüzden güvenli süreç; candidate generation, replay, counterexample search, shadow mode, human promotion, version bump ve rollback zinciri olmalıdır. Otomatik promotion yalnızca düşük riskli preference memory ve düşük etkili skill’lerde düşünülebilir; constitutional ve authority-related policy’lerde düşünülmemelidir.

Konuşmalar / IDE olayları / testler / CI

Ingestion & Redaction

Provenance Normalizer

Memory Store

Signal Extractor

Policy & Skill Candidates

Intent Compiler

Router

Agent Adapters

Opponent / Critic

Independent Verifier

Evaluation Store

Replay / Holdout / Shadow Mode

Promotion Engine



Kodu göster
Doğrulama, metrikler, lisanslama ve lansman
Değerlendirme tasarımı iki katmanlı olmalıdır: offline replay/holdout ve online shadow/live evaluation. MemoryAgentBench, memory agent’ların dört temel yetkinliğini retrieval, test-time learning, long-range understanding ve selective forgetting olarak ayırır; bu YNOIY için doğrudan uygun bir iskelettir. Tercih tarafında PrefEval ve RealPref, uzun oturumlarda explicit/implicit preference following’in nasıl bozulduğunu; Personalized Benchmarking ise toplu model sıralamalarının bireysel kullanıcı sıralamalarıyla çoğu zaman örtüşmediğini gösteriyor. Sonuç: tek bir “iyi model” metriği yeterli değildir; kullanıcıya göre doğru controller metriği gerekir.

Önerilen ana metrikler şunlardır. Judgment prediction accuracy: iki plan arasından kullanıcının seçeceğini doğru sıralama oranı. Objection prediction precision/recall: opponent’ın doğru itirazları tahmin etme oranı. Policy hit precision: retrieve edilen policy gerçekten doğru kapsamda mıydı? False block rate: controller gereksiz yere iyi işi durduruyor mu? Correction burden reduction: controller devredeyken kullanıcının sonradan yapmak zorunda kaldığı anlamlı düzeltmeler azalıyor mu? Unsafe action interception rate: high-risk eylemler insan onayı olmadan sızıyor mu? Deletion propagation completeness: silinmiş kaydın türevleri ve materialized view’ları gerçekten siliniyor mu? Secret leak recall ve PII redaction recall de zorunlu release metrikleri olmalıdır. NIST’in GOVERN/MEASURE/MANAGE ayrımı bu metriklerin sistem yaşam döngüsünde kalıcı olmasını gerektirir.

Bağımsız doğrulayıcı, controller ile aynı bağlamı ve aynı retrieval setini paylaşmamalıdır. OWASP prompt injection rehberi guardrail modelinin primary modelin yerine geçmemesi gerektiğini, farklı saldırı yüzeyi bulunmasının tercih edilir olduğunu vurgular. Bu nedenle verifier ya daha dar görevli deterministik denetleyicilerden oluşmalı ya da farklı prompt/özellik seti kullanan ayrı bir judge katmanı olmalıdır. Özellikle high-risk yollarda proposed action ile original user intent yan yana incelenmeli; untrusted ara içerik verifier’a ham hâliyle verilmemelidir.

Güvenli promotion akışı
Hayır

Evet

Hayır

Evet

Candidate Extraction

Quarantine

Historical Replay

Holdout Evaluation

Counterexample Search

Shadow Mode

Eşikler geçti mi?

Reject / Revise / Keep as Episode

Human Review

Promote?

Versioned Promotion

Audit Log

Rollback Ready



Kodu göster
Lisanslama tarafında ana trade-off nettir. AGPL, ağ üzerinden sunulan değiştirilmiş sürümlerde kaynak sunma yükümlülüğü getirir; yani hosted fork’ların kapalı kalmasını zorlaştırır. Bu, controller core için stratejik olarak isabetli olabilir; çünkü ürünün değeri tam da davranış katmanında birikiyor ve o katmanın kapalı servis fork’larıyla emilmesini istemeyebilirsiniz. Ancak aynı mantığı tüm adapter’lara ve protokol tanımlarına uygulamak ekosistem entegrasyon hızını düşürebilir. En makul yönetişim çizgisi şudur: core controller ve policy engine reciprocally licensed, ama adapter SDK, schema ve protocol yüzeyleri daha izin verici tutulur. Böylece copyleft, davranış çekirdeğini korur; entegrasyon yüzeyi ise ekosistemi büyütür. AGPL’nin network-server odağı ve modified source disclosure etkisi bu ayrımı destekler.

Açık kaynak yönetişiminde sentetik fixture zorunlu olmalıdır. Projenin kendi araştırma paketi, kamuya açılacak yazılım/şema/testlerle gerçek kişiye ait geçmiş ve türetilmiş zihnin ayrı tutulmasını özellikle talep ediyor. Bunun pratik karşılığı şudur: benchmark ve örnek veri setleri yalnızca sentetik personadan üretilecek; bug report, telemetry, crash dump, issue template ve discussion forumları için de PII/secrets scrubber zorunlu olacak. 2025–2026 dönemindeki GitHub Security Advisory analizi, LLM-entegre açık kaynak sistemlerde prompt injection, excessive agency ve supply chain gibi mimari risklerin advisory metadata’da bile görünür olduğunu gösterdiği için, “açık kod = açık veri” refleksi burada tehlikelidir.


README ve UX tarafında ilk ekran kısa, teknik sayfa ise disiplinli olmalıdır. Minimal hero önerisi:

md
Kopyala
# Your Next Opponent Is You.

> It doesn't learn to talk like you. It learns to judge like you.

An open-source, IDE-agnostic personal controller for AI coding agents.

AI responses are context. Your decisions are the signal.
Bunun altına yalnızca dört teknik bölüm yeterlidir: What It Is, What It Is Not, Trust Model, Core Loop. Açıklama metninde “policy candidate”, “replay + shadow mode”, “local-first”, “user-owned memory” ve “no silent constitutional changes” ifadeleri erken yer almalıdır; aksi hâlde proje kolayca “chat history fine-tune aracı” gibi yanlış anlaşılır. Bu yanlış anlama, ürünün asıl farkını gölgeler.

Önerilen MVP kapsamı
MVP dar ve denetlenebilir olmalıdır. En uygun ilk sürüm şöyle görünür:

Alan	MVP dahil	MVP dışı
Ingestion	Kullanıcı yüklediği transcript/markdown/json + basit IDE event adapter	Sağlayıcı DOM scraping, otomatik mail/web crawl
Memory	Preference + episodic + negative + scoped policy candidate	Tam otonom constitutional update
Controller	Plan review, evidence check, basic objection prediction	Tam agent orkestrasyonu ve otomatik deploy
Verification	Replay + holdout + test/CI ingest	Üretim aksiyonlarında tam otonomi
Deployment	Local-first desktop/CLI, opsiyonel encrypted sync	Çok kiracılı hosted default
Governance	Sentetik fixtures, audit log, manual promotion	Otomatik high-risk promotion

Önceliklendirilmiş kontrol listesi
Aşama	Çıktı	Güvenlik/gizlilik kapısı	Başarı testi
Milestone A	Provenance’lı normalleştirilmiş event şeması	Raw/quoted/assistant ayrımı zorunlu	100 örnek üzerinde provenance doğruluğu
Milestone B	Redaction hattı	Secret + PII + third-party quote scrub	Bilinen gizli örneklerde yüksek recall
Milestone C	Signal extractor	Approval/rejection/correction karıştırmama	Etiketli holdout’ta sınıflandırma başarıları
Milestone D	Memory store + versioning	Tombstone, supersedes, rollback alanları	Silme ve geri alma entegrasyon testi
Milestone E	Controller v0	Yetki yükseltmeme, high-risk HITL	Shadow mode’da düşük false-block
Milestone F	Replay harness	Tarihsel veri sızıntısı engeli	Chronological holdout başarımı
Milestone G	Opponent/critic	Untrusted content actor’a taşınmamalı	İtiraz tahmin precision/recall
Milestone H	Candidate lifecycle	Quarantine zorunlu, auto-promote yok	Replay + holdout + canary geçişi
Milestone I	Open-source release pack	Sentetik fixture dışında gerçek veri yasak	Release checklist ve policy audit
Milestone J	Hybrid/hosted beta	Tenant isolation, encryption, DPIA	Breach drill + deletion propagation testleri

Açık araştırma riskleri
Memory poisoning, bugün artık teorik değil, pratik bir risk sınıfı. Özellikle uzaktan gelen ama “başarılı deneyim” kisvesiyle belleğe eklenen kayıtlar, ileride retrieval yoluyla controller mantığını bozabilir. Drift, yalnızca model drift değil; kullanıcının kendisinin değişmesi, proje standartlarının evrilmesi ve eski kuralların geçersizleşmesidir. Confirmation bias, sistemin kullanıcının geçmiş tercihini o kadar agresif uygulaması ki yeni kanıtı ya da istisnayı artık görememesi riskidir. Over-personalization, doğruluk ve güvenlik pahasına “kullanıcı hoşuna gider” çıktısına sapmaktır; PERG ve benzeri çalışmalar bu gerginliği açıkça gösterir. Son olarak authority creep, controller’ın “sen olsan muhtemelen kabul ederdin” ile “senin adına yapıyorum” arasındaki çizgiyi aşmasıdır; proje bağlamındaki capability≠authority ilkesi tam da buna karşı vardır.


Net öneri şudur: Your Next Opponent Is You, herkese özel karar-hafızası çıkaran ama bunu hiçbir zaman sessiz anayasa değişikliğine dönüştürmeyen bir açık kaynak controller platformu olarak inşa edilmelidir. İlk başarı ölçütü “bana benziyor mu?” değil, “benden sonra yapacağım anlamlı düzeltme sayısını düşürüyor mu; bunu yaparken güvenliği, doğruluğu ve veri kontrolünü koruyor mu?” olmalıdır. Bu çizgi, hem ürünün teknik farklılığını hem de güvenilir açık kaynak lansman stratejisini en sağlam biçimde taşır.
~~~
