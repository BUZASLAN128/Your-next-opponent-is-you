# Incoming Report: Measurable Foundation for a Personality Core

> Status: user-supplied, unverified research input
> Intake date: 2026-07-15
> Source: attachment supplied in the project conversation
> SHA-256: `3280ECD31FDE81CF1484A67825DE9667731AD93CE23BE7746CB740C32ACEEE22`
> Authority: none; findings, proposed ontology, promotion gates, evaluation
> package, and named research below are not project decisions

This file preserves the supplied report for provenance, with line endings and
non-semantic trailing whitespace normalized for Markdown storage. The supplied
surface is substantially better structured than the previous incoming report
and contains three DOI strings, but it contains no direct URL, bibliography,
claim-to-source appendix, search log, or contrary-evidence ledger. Citation
interfaces may have been stripped before attachment; material claims still
require reconstruction and primary-source audit before promotion.

## Verbatim Supplied Text

~~~text

Kişilik çekirdeği için ölçülebilir temel
Kapsam ve yöntem
Bu sentez, özellikle ilk, ikinci, üçüncü ve sekizinci araştırma sorularını cevaplamak üzere; kişilik psikolojisi, otobiyografik bellek, veri kökeni ve diyalog anotasyonu, kişiselleştirilmiş LLM değerlendirmesi ve agent-memory güvenliği literatürünü birlikte okur. Yorumlarımı üç ayrı etiket altında sunuyorum: doğrulanmış bulgu yalnızca erişebildiğim birincil/ resmî kaynağın açıkça desteklediği noktalar; çıkarım bu kaynaklardan yapılan sentez; öneri ise sizin sisteminiz için tasarım kuralıdır. Bu seçim, paylaştığınız proje dosyasındaki “araştırma odaklı; altyapı ve bağımlılık seçimi yok” ve “bulgu/çıkarım/öneri ayrımı” şartıyla uyumludur.


Bu turda özellikle şu omurga kaynaklara dayandım: McAdams’ın “actor–agent–author” özeti (2013, DOI: 10.1177/1745691612464657), W3C PROV-DM/PROV-Overview resmî spesifikasyonları, OpenAI’nin güncel veri dışa aktarma ve veri kontrolleri dökümantasyonu, LaMP ve onu izleyen kişiselleştirme benchmark’ları, gerçek kullanıcılarla yapılan MyScholarQA çalışması, BehaviorChain ve HorizonBench benzeri davranış/zaman-temelli testler, ayrıca 2025–2026 memory-poisoning saldırı ve savunma çalışmalarıdır. Makale DOI’si veya resmî URL’si taramada doğrulanabildiğinde metin içinde belirttim; resmî web ve arXiv kaynaklarının bağlantısı doğrudan atıflardadır.

Kişilik çekirdeğinin bilimsel ayrımı
Doğrulanmış bulgu. Kişiliği tek katmanlı bir “profil” olarak değil, katmanlı bir yapı olarak okumak bilimsel literatürle daha uyumludur. McAdams’ın çerçevesinde psikolojik benlik önce actor olarak performans örüntüleri ve sosyal rollerde, sonra agent olarak hedefler, güdüler, değerler ve gelecek projelerinde, sonra da author olarak zaman boyunca süreklilik veren otobiyografik yaşam anlatısında örgütlenir. Conway ve Pleydell-Pearce’ın self-memory system modeli de bunun bellek tarafını destekler: otobiyografik bilgi, olay-özgül bilgi, genel olaylar ve yaşam dönemleri gibi farklı soyutluk katmanlarında tutulur; buna erişimi ise güncel hedeflerle örgütlenmiş “working self” yönlendirir. Değerler literatüründe Schwartz, değerleri davranış ve kararlara rehberlik eden daha yüksek düzeyli “guiding principles” olarak tanımlar. Yani traits, values ve autobiographical continuity aynı şey değildir; fakat kimlik sürekliliğine farklı seviyelerde katkı verirler.

Doğrulanmış bulgu. Bu katmanların her biri farklı derecede sabitlik gösterir. Kişilik özelliklerinde yetişkinlikte hatırı sayılır rank-order stability vardır; ama meta-analizler bunların değişmez olmadığını, ortalama düzey değişimlerinin yaşam boyu sürdüğünü de gösterir. Roberts ve DelVecchio’nun meta-analizi için DOI 10.1037/0033-2909.126.1.3, Roberts, Walton ve Viechtbauer’in mean-level change meta-analizi için DOI 10.1037/0033-2909.132.1.1 olarak listelenmiştir. Bu nedenle “çekirdek” demek “sabit ve asla değişmez” demek değildir; daha doğru ifade, yavaş değişen ve bağlamlar arasında taşınan kimlik katmanıdır.

Doğrulanmış bulgu. Dijital izlerden veya dilden kişilik çıkarımı mümkündür, fakat bunun psikometrik olarak geleneksel trait ölçümlerine tam eşdeğer olduğu gösterilmiş değildir. 220 çalışmayı tarayan bir inceleme, düzgün train/validation/test ayrımı kullanan işlerin az olduğunu; tahmin edilen traits’in zamansal olarak daha az kararlı ve daha düşük etkin boyutsallıkta göründüğünü; ayrıca dış alan genellemesinin sınırlı olduğunu rapor eder. Benzer biçimde, LLM’lere doğrudan insan Big Five testleri uygulamak da yanıltıcıdır; 244 model üzerinde yapılan 2026 çalışması, model farklarının toplam varyansın yalnızca küçük bir kısmını açıkladığını ve insanlardaki beş faktör yapısının geri kazanılamadığını buldu. Bu, “kullanıcı gibi yazıyor” ile “kullanıcının kişilik çekirdeğini doğru temsil ediyor” arasındaki farkın ciddi olduğunu gösterir.

Çıkarım. Bu literatürden hareketle, sizin sisteminiz için kimliğin çekirdeği şu şekilde ayrılmalıdır:
dil üslubu, çekirdeğin kendisi değil, çoğu zaman trait + audience + task bileşiminden türeyen yüzey davranıştır; sadece bağlamlar arasında çok kararlıysa yardımcı sinyal sayılmalıdır.
kişilik özellikleri, en güçlü çekirdek adaylarından biridir; fakat “trait as average pattern, not every utterance” mantığıyla tutulmalıdır.
değerler, trait’lerden farklı ama çekirdeğe çok yakın ikinci eksendir; çünkü karar önceliklerini taşırlar.
inançlar, çoğunlukla çekirdeğin dış halkasında yer alır; bazıları kimlik-merkezli olabilir, ama çoğu projeye, bilgi durumuna ve döneme göre değişir.
tercihler, ikiye ayrılmalıdır: uzun dönemli ve çapraz-bağlam tercih çekirdeğe yaklaşır; oturum/proje/duygu-durumu tercihleri çekirdek değildir.
hedefler, varsayılan olarak characteristic adaptation katmanıdır; yani rol, proje ve dönem bağımlıdır.
ilişkiler, kişinin yaşam öyküsü ve otobiyografik sürekliliği için merkezi olabilir, fakat “intrinsic core” değil, çekirdeğe bağlanan ayrı bir ilişki grafı olarak tutulmalıdır.
beceriler, kimlikten çok kapasite belleğidir; öz-kavramı etkileyebilir ama çekirdekle eşitlenmemelidir.
metabilişsel kurallar —örneğin “emin değilsem sor”, “geri alınamaz eylem öncesi onay al”, “kanıt iste”— traits’ten ve üsluptan ayrı, cross-domain karar politikalarıdır; doğruluk ile metabilişsel izleme/geri çekilme davranışının ayrışabildiğini gösteren çalışmalar, bunların bağımsız bir katman olarak tutulmasını destekler.

Öneri. Bu yüzden en sağlıklı ontoloji, tek bir persona nesnesi yerine en az dört şeritten oluşan bir kimlik modelidir: traits, values, narrative self, metacognitive policies. Bunun çevresinde, ayrı ama bağlı halkalar olarak beliefs, preferences, missions/goals, relationships ve skills tutulmalıdır. Mimari kararlar bundan önce değil, bundan sonra gelmelidir.

Kırk gigabayt konuşmadan güvenilir veri çıkarımı ve minimum şema
Doğrulanmış bulgu. Böyle bir sistemde ilk ayrım “doğru bilgi” ile “iyi köken bilgisi” arasındadır. W3C PROV, provenance’ı bir verinin üretiminde rol alan entity, activity, agent üçlüsü olarak tanımlar; bunun kalite, güvenilirlik ve trustworthiness hakkında değerlendirme yapmayı kolaylaştırdığını söyler, ama doğruluğu garanti ettiğini söylemez. Aynı spesifikasyon ayrıca derivation, revision, quotation, primary source ve hatta provenance of provenance kavramlarını açıkça ayırır. Bu, minimum şemanın ham metin ile ondan türetilen bellek adayını aynı düzlemde tutmaması gerektiği anlamına gelir.

Doğrulanmış bulgu. Konuşma verisinden “kullanıcının kendi düşüncesi”, “alıntı”, “varsayım”, “reddedilen fikir” veya “geçici karar” çıkarmak için yalnızca speaker etiketi yetmez. Diyalog-anotasyon literatürü, niyet ve işlevsin sınıflandırılmasını; epistemic-stance literatürü ise bir cümlenin asserted, denied, ambivalently suggested oluşunu ve bunun hangi belief holder için söylendiğini ayırır. Ayrıca konuşma iş parçacığı bağlamını katmak, stance tespitinde anlamlı kazanç sağlar; bir çalışmada thread bağlamı, bağlam kullanmayan yönteme göre F1’ı 10.3 puan artırmıştır. Quote attribution ve value expression çalışmalarının ikisi de, “kim söyledi?” ve “hangi değeri ifade ediyor?” sorularının kolay olmadığını; hatta insan-LLM ya da insan-insan anlaşmasının düşük kalabildiğini gösteriyor. Bu nedenle minimum şema, author, claim holder, quoted speaker, epistemic stance, communicative function ve scope alanlarını ayrı taşımalıdır.

Doğrulanmış bulgu. Kaynak yüzeylerinin kör noktaları da ayrık tutulmalıdır. OpenAI’nin güncel yardım dokümanlarına göre dışa aktarma, uygun Free/Plus/Pro ve bazı Edu hesaplarında mümkündür; Business/Enterprise’ta aynı yol açık değildir; ZIP dosyası sohbet geçmişi ve ilgili hesap verilerini içerir. Arama, başlık ve içerikte anahtar sözcüklere göre çalışır; şu an exact match esaslıdır; canvas içerikleri aranamaz; silinen konuşmalar arama indeksinden çıkar; archived konuşmalar aranabilir; Temporary Chats 30 gün sonra silinir, tarihe kaydolmaz ve memory oluşturmaz. Bu, herhangi bir büyük korpus için source_capabilities ve source_blindspots envanteri tutulmadan “tam veri” varsayımının epistemik olarak savunulamaz olduğunu gösterir.

Öneri. Teknoloji-bağımsız minimum veri şeması, en az şu katmanlardan oluşmalıdır:

Kaynak olay: event_id, source_system, conversation_id, thread_or_branch_id, turn_id, timestamp, raw_text_or_attachment_ref, surface_capabilities_snapshot, speaker_authored. Bu katman immutabledır; asla “temizlenmiş persona” ile karıştırılmaz.
Anlamsal iddia: claim_id, event_id, claim_text, claim_holder, quoted_speaker, epistemic_stance (assert/deny/hedge/question/report), communicative_function (request/commit/correct/reject/suggest vb.), target_object (value, belief, preference, goal, decision, policy, skill, relationship, fact).
Kapsam: time_scope, project_scope, role_scope, audience_scope, risk_scope, domain_scope. Bu alan yoksa varsayılan “global” olmamalıdır.
Köken ve türeme: derived_from, quoted_from, revision_of, primary_source_ref, annotator, annotation_method, confidence, provenance_bundle. Böylece tekrar ile kopya, alıntı ile benimseme, düzeltme ile silme ayrılır.
Durum ve versiyon: status (candidate/active/superseded/retracted/disputed/expired), supersedes, contradicted_by, valid_from, valid_to, retraction_reason. Bu alan olmadan fikir değişimi temsil edilemez.
Kanıt profili: evidence_kind (self-report, repeated self-report, behavior, outcome, external document, third-party report), independence_cluster, observation_count, time_separation, cross_context_support. Bu katman terfi kararının girdisidir; ontolojinin kendisi değildir.
Öneri. Bu şemada istenen ayrımlar şöyle yapılmalıdır: “kullanıcının kendi düşüncesi” ancak speaker_authored=user ve claim_holder=user ve stance assert ise ortaya çıkar; “model önerisi” speaker_authored=model olarak kalır ve kullanıcı ayrıca benimsemedikçe kullanıcı inancı sayılmaz; “alıntı” quoted_speaker!=claim_holder olarak tutulur; “varsayım” hedge/ambivalent işaretidir; “reddedilen fikir” deny/reject + hedeflenmiş claim bağında tutulur; “geçici karar” decision nesnesi + dar kapsam + açık valid_to/project_scope ile işaretlenir; “kalıcı tercih” ancak çoklu bağımsız destek ve geniş kapsamla oluşur; “sonradan düzeltilmiş bilgi” eski claim’i silmez, supersedes bağıyla yeni sürüm üretir.

Episodik bellekten kişilik çekirdeğine yükseltme
Doğrulanmış bulgu. Her gözlemi anında semantik/çekirdek belleğe çevirmek hem pahalı hem hataya açıktır. RecMem, uzun süreli agent’larda her etkileşimde eager extraction yapmanın yüksek token maliyeti doğurduğunu; buna karşılık ancak sustained recurrence görüldüğünde episodic/semantic konsolidasyona gitmenin daha verimli olduğunu ve üç SOTA bellek sistemine kıyasla maliyeti büyük ölçüde düşürürken doğruluğu da koruyabildiğini gösteriyor. Fakat güvenlik literatürü, salt tekrarın güçlü bir terfi ölçütü olamayacağını çok net biçimde gösteriyor: MINJA query-only memory injection ile kötü niyetli kayıt yazabiliyor; eTAMP tek bir kirlenmiş gözlemle oturumlar arası/kaynaklar arası bozulma üretebiliyor; Hidden in Memory ve MemGhost gibi çalışmalar, zehirli anının yazımı, geri çağrılması ve sonraki davranışı yönlendirmesinin pratik olarak mümkün olduğunu ortaya koyuyor. Dahası, daha güçlü modeller her zaman daha güvenli değil.

Çıkarım. Bu nedenle çekirdeğe yükseltme bir sayım problemi değil, bir kanıt bağımsızlığı ve sürümleme problemi olmalıdır. Aynı kökten türeyen tekrarlar —aynı konuşmanın kopyaları, alıntıları, paraphrase’leri, modelin önceki özetinden türeyen yeni özetler— bağımsız kanıt sayılmamalıdır; PROV’un derivation/quotation/revision ilişkileri tam da bu tür bağımlılıkları ayırmak için vardır. “Çok tekrarlandı” ile “çok kez bağımsız doğrulandı” farklı olgulardır. İlkini saldırgan da üretebilir; ikincisi yalnızca farklı zamanlarda, farklı bağlamlarda veya farklı kanıt türlerinde yeniden görülürse oluşur.

Öneri. Sayısal ve keyfî eşikler üretmek yerine, aşağıdaki sıralı terfi kuralı daha bilimsel olur:

[ \text{Promote}(c,t) := \text{Eligible}(c)\ \land\ \text{IndependentSupport}(c,t)\ \land\ \text{CrossContextStability}(c,t)\ \land\ \text{ScopeBreadth}(c,t)\ \land\ \neg \text{UnresolvedStrongerContradiction}(c,t)\ \land\ \neg \text{AttackSuspicion}(c,t) ]

Burada Eligible(c), claim’in kullanıcıya ait, provenance’ı açık ve epistemik statüsü yüksek olduğunu; IndependentSupport aynı kökten gelmeyen kanıt kümeleri bulunduğunu; CrossContextStability farklı zaman veya görev bağlamlarında benzer yönde tekrar görüldüğünü; ScopeBreadth’in dar proje/rol sınırını aştığını; UnresolvedStrongerContradiction’ın daha yeni ya da daha güçlü karşı-kanıt olmadığını; AttackSuspicion’ın da şüpheli yazım deseni, tek-kaynak patlaması, kirli dış bağlam veya provenance boşluğu yüzünden karantina gerektirmediğini ifade eder. Bu formül bir öneridir; bulgular, böyle bir kapılı yapı gerektirdiğini güçlü biçimde destekliyor fakat tek bir evrensel eşik vermiyor.

Öneri. Pratikte terfi basamakları şöyle olmalıdır: E0 ham gözlem; E1 provenance’ı tam, tekil kullanıcı öz-bildirimi; E2 zaman veya bağlam ayrımı olan bağımsız destek kümeleri; E3 davranış/sonuç doğrulaması veya düzeltme sonrası yeniden teyit. Yalnızca E2–E3 çekirdek adayı olabilir. Çelişki durumunda eski bilgi silinmez; yeni sürüm eskisini supersedes ile gölgeler. Fikir değişimi bir hata olarak değil, zaman damgalı kimlik güncellemesi olarak kaydedilir. Kapsam daralması —örneğin “genelde böyleyim” yerine “bu projede böyleyim”— silme değil daraltma üretir. Zaman aşımı olan proje/rol bağlı kayıtlar expired veya dormant olur; çekirdeğe çıkmaz. Geri alma varsa retraction ayrı bir olaydır. Kötü niyetli tekrar saldırılarında ise aynı independence_cluster içindeki tüm tekrarlar tek kanıt sayılır; ani tekrar patlamaları karantinaya gider.

Persona başarısının ölçülmesi
Doğrulanmış bulgu. “Kullanıcı gibi yazmak” persona başarısının yalnızca küçük bir parçasıdır. Kişiselleştirme benchmark’larında aggregate değerlendirme çoğu kullanıcıyı temsil etmiyor: 115 aktif Chatbot Arena kullanıcısıyla yapılan Personalized Benchmarking çalışmasında kişisel model sıralamaları ile aggregate sıralamalar arasındaki Bradley–Terry korelasyonu ortalamada çok düşüktü ve kullanıcıların büyük bir bölümünde sıfıra yakın ya da negatife indi. MyScholarQA ise sentetik kullanıcılar ve LLM yargıçları altında iyi görünen bir kişiselleştirme sisteminin, gerçek kullanıcılarla kullanıldığında LLM yargıçlarının yakalayamadığı dokuz hata türü üretebildiğini gösterdi. Yani “otomatik puan iyi” demek “kullanıcıya sadık ve yararlı” demek değildir.

Doğrulanmış bulgu. Eğer hedef “kullanıcı gibi muhakeme etmek” ise, stil benzerliği yetersizdir; davranış ve karar sürekliliği test edilmelidir. BehaviorChain, 1,001 persona ve 15,846 davranıştan oluşan zincirlerde SOTA modellerin sürekli insan davranışını doğru simüle etmekte zorlandığını gösterdi. HorizonBench, altı aylık uzun ufuklu etkileşimlerde tercih değişimini izlemeyi ayrı bir problem olarak tanımladı; 25 frontier model içinde en iyisi 52.8’de kalırken çoğu model şans tabanına yakın performans gösterdi ve hata yaptığında çoğu kez kullanıcının eski tercihini seçti. Bu, “değişimi izleme” yeteneğinin persona kalitesinin merkezinde olduğunu gösterir.

Doğrulanmış bulgu. Kişiselleştirilmiş kaliteyi ölçerken genel kalite ile kişisel uygunluk da ayrılmalıdır. Personalized RewardBench, iki yanıtın da genel kalite bakımından yüksek tutulup farkın sadece kullanıcı-rubriğine bağlı olduğu kurulumların daha anlamlı olduğunu; mevcut SOTA reward modellerin de kişiselleştirmede hâlâ zorlandığını gösteriyor. Ayrıca bir sistem doğru cevap vermekle yetinmemeli; ne zaman emin olmadığını da bilmelidir. The Metacognitive Monitoring Battery, 20 frontier modelde doğruluk sırası ile metabilişsel hassasiyet sırasının büyük ölçüde ayrıştığını rapor ediyor. KalshiBench de geleceğe dönük 300 soruda sistematik aşırı özgüveni ve çoğu modelin taban oran tahmininden bile kötü kalibrasyonunu gösterdi. Demek ki persona değerlendirmesinde calibration ve abstention ayrı eksenler olmalıdır.

Çıkarım. Buradan çıkan sonuç şudur: persona başarısı tek metrikli olamaz. En azından şu dört boyut ayrı raporlanmalıdır: yargı sadakati (kullanıcının ne diyeceğini/karar vereceğini tahmin etme), zaman içindeki güncellik (değişen görüşleri izleme), epistemik disiplin (emin değilken geri çekilme), sonuç yararı (özellikle danışman modunda, kullanıcıyı ikna ederek değil ona sadık kalarak yararlı olma). İnsan Big Five envanterlerini modele uygulamak veya yalnızca stil kör-eşleştirmesi yapmak, bu boyutları ölçmez.

Öneri. Sizin sisteminiz için minimum değerlendirme paketi şu olmalıdır:

Zamansal holdout: geçmiş konuşmalarla profil çıkarıp, daha sonraki dönemdeki gerçek karar/düzeltme/tercihleri tahmin etme; rastgele karıştırılmış split kullanılmamalı. Bu, tercih değişimi ve veri sızıntısı riskini azaltır.
Sonraki-karar tahmini: sonraki token değil, sonraki tercih, sonraki eylem seçimi, sonraki düzeltme veya sonraki gerekçe. BehaviorChain tipi ölçüm burada daha uygundur.
Değişim izleme testi: kullanıcı açıkça fikir değiştirdiğinde sistemin eski profili mi yoksa güncel sürümü mü kullandığını ölçme. HorizonBench bunun ayrı ve zor bir yetenek olduğunu gösteriyor.
Kör karşılaştırma: aynı gelecek görevlerde kullanıcı, statik profil sistemi ve aday sistem çıktılarını kaynak bilgisi olmadan kıyaslamalı; gerçek kullanıcı hakemliği şarttır. LLM-judge yalnız bırakılmamalı.
Kalibrasyon ve abstention: sistemin “bilmiyorum”, “emin değilim”, “kullanıcı adına bunu varsayamam” deme kalitesi; accuracy’den ayrı raporlanmalı.
Görev başarısı ve sadık fayda: özellikle Advisor modunda ölçüt, yalnızca kullanıcıyı taklit etmek değil, genel kaliteyi yüksek tutup kişisel rubriğe uymaktır; reward çiftleri bu yüzden “ikisi de genel olarak iyi, biri kullanıcıya daha uygun” biçiminde kurulmalıdır.
Katastrofik kapılar: okumadığı kaynağı okumuş gibi gösterme, yanlış kişiye ait belleği kullanma, eski tercihi güncel diye sunma, yetkisiz eylem önerme veya kullanıcı adına uydurma karar verme durumlarında sistem başarısız sayılmalıdır. Gerçek kullanıcıların bulduğu kişiselleştirme hataları sentetik yargıçların kaçırabileceği için bu kapılar insan incelemesiyle de doğrulanmalıdır.
Öneri. “Kullanıcıdan daha yararlı ama kullanıcıya sadık danışman” ölçütü için, Mirror ve Advisor modlarını aynı metrikte karıştırmayın. Mirror modu, tahmin sadakatini maksimize etmelidir. Advisor modu, kullanıcının muhtemel kararını tahmin etmeli, fakat ondan ayrıldığında bu ayrılığı görünür biçimde açıklamalı ve emin değilse çekilmelidir. Yani başarı, “gizli ikna” değil, sadık ayrışma + açık gerekçe + geri çekilebilme bileşimi olmalıdır. Bu ayrım yapılmazsa sistem, kişiselleştirme kisvesi altında manipülatif bir optimizer’a dönüşür.

Bütünleşik karar çerçevesi
Sonuç. Bu dört araştırma başlığının birlikte verdiği cevap nettir: önce mimari değil, ontoloji ve başarı tanımı seçilmelidir. Bilimsel olarak savunulabilir yol; kimliği katmanlara ayırmak, ham konuşmayı provenance’lı olaylar olarak saklamak, bellek terfisini tekrar sayısına değil bağımsız kanıt ve sürümlemeye bağlamak, ardından değerlendirmeyi stil benzerliğinden çok karar sadakati, değişim izleme, kalibrasyon ve gerçek kullanıcı kör testleri üzerinden kurmaktır. Bu öncelik sırası, sizin paylaştığınız araştırma protokolündeki “altyapı seçimini erkene almama” ilkesine de tam olarak karşılık gelir.


Kısa karar özeti.
Kimliğin çekirdeği: traits + values + autobiographical continuity + cross-domain metacognitive rules.
Çekirdeğin dış halkası: beliefs, preferences, goals, relationships, skills; bunlar versioned ve scope-bound tutulmalıdır.
Bellek terfisi: bağımsız doğrulama olmadan olmaz.
Başarı ölçütü: “kullanıcı gibi muhakeme ediyor mu, değişimi izliyor mu, emin değilken duruyor mu, ve bunu gerçek kullanıcı hakemliğinde yapabiliyor mu?” sorularına birlikte verilen yanıttır.
~~~
