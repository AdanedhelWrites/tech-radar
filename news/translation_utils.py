"""
Teknoloji Radar — Ortak Ceviri Modulu
=====================================
Tum scraper'larin kullandigi merkezi ceviri altyapisi.
Ceviri saglayici zinciri + terim koruma + Turkce imla post-processing.

Kullanim:
    from news.translation_utils import translate_text, translate_long_text

Neden tek modul?
    - 5 farkli scraper'da tekrarlanan kod vardi
    - PROTECTED_TERMS listesi tutarsizdi
    - Post-processing hicbirinde yoktu
"""

import os
import re
import time
from typing import Dict, Iterable, List, Optional, Set, Tuple

# ============================================================
# 1. KORUNACAK TEKNIK TERIMLER
# ============================================================
# Bu terimler ceviri sirasinda placeholder ile degistirilir
# ve ceviri sonrasi geri konulur. Boylece saglayici
# bunlari bozamaz.
#
# KURAL: Sadece "tam kelime" (word-boundary) olarak eslesenler
# korunur. 2 karakterden kisa terimler word-boundary olmadan
# kelimelerin icinde eslesebilir ("again" -> "aGAin") bu yuzden
# kisa kisaltmalar dikkatli secilmeli.
# ============================================================

PROTECTED_TERMS = [
    # --- Urunler / Markalar ---
    'MinIO', 'Seq', 'Ceph', 'MongoDB', 'PostgreSQL', 'RabbitMQ',
    'Elasticsearch', 'Kibana', 'Redis', 'Moodle', 'Kafka', 'Cassandra',
    'Logstash', 'Beats', 'Filebeat', 'Metricbeat', 'Lucene',
    'OpenSearch', 'Splunk', 'Datadog', 'PagerDuty', 'OpsGenie',
    'Prometheus', 'Grafana', 'Jaeger', 'Zipkin', 'OpenTelemetry',
    'Nginx', 'HAProxy', 'Envoy', 'Istio', 'Linkerd',
    'Jenkins', 'ArgoCD', 'Argo CD', 'Argo',
    'Terraform', 'Ansible', 'Vagrant', 'Packer',
    'GitHub', 'GitLab', 'Bitbucket',

    # --- Cloud / Platform ---
    'AWS', 'GCP', 'Azure', 'CloudFlare', 'Cloudflare',
    'Kubernetes', 'Docker', 'Helm', 'Podman',

    # --- Kubernetes Kavramlari ---
    'pod', 'pods', 'node', 'nodes', 'kubelet', 'kubeadm', 'kubectl',
    'kube-proxy', 'kube-apiserver', 'kube-controller-manager', 'kube-scheduler',
    'StatefulSet', 'StatefulSets', 'DaemonSet', 'DaemonSets',
    'ReplicaSet', 'ReplicaSets', 'Deployment', 'Deployments',
    'ResourceClaim', 'ResourceClaims', 'ResourceSlice',
    'EndpointSlice', 'EndpointSlices',
    'ConfigMap', 'ConfigMaps', 'Secret', 'Secrets',
    'PersistentVolume', 'PersistentVolumeClaim',
    'StorageClass', 'StorageClasses', 'Namespace', 'Namespaces',
    'ClusterRole', 'ClusterRoleBinding',
    'NodePrepareResources', 'NodeUnprepareResources',
    'CronJob', 'CronJobs', 'Job', 'Jobs',
    'Ingress', 'IngressClass',
    'HorizontalPodAutoscaler', 'VerticalPodAutoscaler',

    # --- Networking ---
    'IPv4', 'IPv6', 'IPVS', 'iptables', 'winkernel',
    'dual-stack', 'PreferDualStack', 'RequireDualStack',
    'LoadBalancer', 'load balancer',

    # --- Protokoller ---
    'API', 'REST', 'gRPC', 'GraphQL', 'HTTP', 'HTTPS',
    'DNS', 'CDN', 'TCP', 'UDP', 'WebSocket',
    'AMQP', 'MQTT', 'LDAP', 'SAML', 'OAuth', 'JWT', 'TLS', 'SSL',
    'SSH', 'FTP', 'SFTP', 'NFS', 'SMB', 'iSCSI',

    # --- Veritabani / Storage ---
    'SQL', 'NoSQL', 'PostgreSQL', 'MySQL', 'MariaDB', 'SQLite',
    'PGPool', 'pgvector', 'VACUUM', 'WAL', 'MVCC',
    'RADOS', 'RGW', 'CephFS', 'BlueStore', 'OSD',
    'Erasure Coding', 'Object Storage', 'Block Storage',
    'Replication', 'Sharding', 'Clustering', 'Failover',

    # --- Guvenlik ---
    'CVE', 'CVSS', 'XSS', 'CSRF', 'SSRF',
    'SELinux', 'RBAC', 'AppArmor',
    'OWASP', 'NIST', 'MITRE',
    'zero-day', 'Zero-Day',

    # --- SRE / DevOps ---
    'SRE', 'SLO', 'SLA', 'SLI',
    'MTTR', 'MTTF', 'MTTD', 'MTBF',
    'DevOps', 'DevSecOps', 'GitOps',
    'CI/CD', 'Toil', 'Runbook', 'Playbook', 'Postmortem', 'Post-mortem',
    'On-call', 'Oncall', 'On-Call',
    'Chaos Engineering', 'Chaos Monkey',
    'Auto-scaling', 'Autoscaling',
    'Microservices', 'Monolith',
    'Observability', 'Monitoring', 'Alerting',
    'IaC', 'Infrastructure as Code',

    # --- AI / Yapay Zeka ---
    'LLM', 'AI', 'AGI', 'RAG', 'LoRA', 'Transformers', 'Transformer', 'GenAI', 
    'Prompt', 'Token', 'Fine-tuning', 'Embeddings', 'LangChain', 
    'LlamaIndex', 'Hugging Face', 'PyTorch', 'TensorFlow', 'OpenAI',
    'Anthropic', 'Claude', 'GPT-4', 'Gemini', 'Midjourney', 'Stable Diffusion',
    'Benchmark', 'Leaderboard', 'MMLU', 'HumanEval',

    # --- Surumler / Etiketler ---
    'RELEASE', 'LTS', 'GA', 'RC', 'Beta', 'Alpha',
    'CHANGELOG',

    # --- Donanim / Birimler ---
    'CPU', 'GPU', 'RAM', 'SSD', 'HDD', 'NVMe',
    'GB', 'TB', 'MB', 'KB',

    # --- Programlama / Diller ---
    'Go', 'Rust', 'Python', 'Java', 'JavaScript', 'TypeScript',
    'Node.js', 'npm', 'yarn', 'pip', 'cargo',
    'goroutine', 'goroutines',
    'async', 'await', 'callback', 'promise',

    # --- OS ---
    'Linux', 'Ubuntu', 'CentOS', 'RHEL', 'Debian', 'Alpine',
    'Windows', 'macOS', 'FreeBSD',

    # --- Egitim / LMS (Moodle) ---
    'SCORM', 'LTI', 'IMSCP', 'JIRA',

    # --- CNCF / Diger ---
    'CNCF', 'etcd', 'Patroni', 'CloudNativePG', 'Harbor',
    'feature gate',
    'DRA', 'HNS', 'hnslib',
]

# Tekrarlanan terimleri kaldir, siralamayi koru
_seen = set()
_unique_terms = []
for _t in PROTECTED_TERMS:
    if _t not in _seen:
        _seen.add(_t)
        _unique_terms.append(_t)
PROTECTED_TERMS = _unique_terms


# ============================================================
# 2. TERIM KORUMA MEKANIZMASI
# ============================================================
# Placeholder formati: XTRM0001X, XTRM0002X, ...
# "XTRM" on eki hicbir saglayici tarafindan tercume edilmez
# cunku bilinmeyen bir harf dizisi. Sayisal kisim benzersizlik saglar.
# ============================================================

_PLACEHOLDER_RE = re.compile(r'XTRM\d{4}X')
# Saglayici yer tutucuyu bosluklu veya kucuk harfli dondurebilir: 'xtrm 0001x', 'X TRM0001 X'
_BROKEN_PLACEHOLDER_RE = re.compile(r'[Xx]\s*[Tt]\s*[Rr]\s*[Mm]\s*(\d{4})\s*[Xx]')


def _repair_placeholders(text: str) -> str:
    """Saglayicinin bozdugu yer tutuculari standart bicime getirir.

    Geri koymadan ONCE cagrilmalidir; sonra cagrilirsa onarilan kod artik hic
    geri konamaz ve ceviride ham 'XTRM0001X' kalir.
    """
    return _BROKEN_PLACEHOLDER_RE.sub(r'XTRM\1X', text)


def _protect_terms(text: str) -> Tuple[str, Dict[str, str]]:
    """
    Teknik terimleri placeholder ile degistirir.
    Ayrica: backtick kod parcalari, PR referanslari, URL'ler, surumler.
    Return: (korunmus_metin, geri_donus_sozlugu)
    """
    replacements: Dict[str, str] = {}
    counter = [0]

    def _make_ph():
        counter[0] += 1
        return f"XTRM{counter[0]:04d}X"

    def _replace_match(m):
        ph = _make_ph()
        replacements[ph] = m.group(0)
        return ph

    result = text

    # 1) Backtick icindeki kod parcalari: `kubectl get pods`
    result = re.sub(r'`[^`]+`', _replace_match, result)

    # 2) PR referanslari: (#123456, @user) [SIG ...]
    result = re.sub(
        r'\(#\d+,\s*@[\w-]+\)\s*\[SIG [^\]]+\]',
        _replace_match, result
    )

    # 3) Tek basina SIG etiketleri: [SIG Node], [SIG Network and Windows]
    result = re.sub(r'\[SIG [^\]]+\]', _replace_match, result)

    # 4) GitHub URL'leri ve paket isimleri
    result = re.sub(r'https?://\S+', _replace_match, result)
    result = re.sub(r'github\.com/[\w./-]+', _replace_match, result)

    # 4b) Bos parantezli cagrilar: parse_array(), Element_Classes::parse_array(), obj.run()
    result = re.sub(
        r'\b[A-Za-z_][A-Za-z0-9_]*(?:(?:::|\.)[A-Za-z_][A-Za-z0-9_]*)*\(\)',
        _replace_match, result
    )

    # 4c) Alt cizgili tanimlayicilar: tribe_events, pg_stat_lock
    # LibreTranslate alt cizgiyi siler; diger saglayicilar da zaman zaman kelimelere boler.
    result = re.sub(r'\b[A-Za-z][A-Za-z0-9]*(?:_[A-Za-z0-9]+)+\b', _replace_match, result)

    # 5) Surum numaralari: v1.2.3, 9.3.1, 2025.2
    result = re.sub(r'\bv?\d+\.\d+(?:\.\d+)*(?:-[\w.]+)?\b', _replace_match, result)

    # 6) CVE numaralari: CVE-2024-12345
    result = re.sub(r'CVE-\d{4}-\d{4,}', _replace_match, result)

    # 7) Korunan teknik terimleri (kelime sinirli, uzundan kisaya)
    for term in sorted(PROTECTED_TERMS, key=len, reverse=True):
        # Kelime siniri ile eşleştir - kisa terimlerin kelime icinde eslesmesin
        pattern = r'\b' + re.escape(term) + r'\b'
        try:
            matches = list(re.finditer(pattern, result))
            for m in reversed(matches):
                ph = _make_ph()
                replacements[ph] = m.group(0)
                result = result[:m.start()] + ph + result[m.end():]
        except re.error:
            pass

    return result, replacements


def _restore_terms(text: str, replacements: Dict[str, str]) -> str:
    """Placeholder'lari orijinal terimlerle geri degistirir.

    Sira onemlidir: bir yer tutucunun degeri yalnizca kendisinden ONCE
    olusturulmus yer tutuculari icerebilir (orn. URL deseni onceden korunmus bir
    kod parcasinin kodunu yutar). Bu yuzden en son olusturulandan ilkine dogru
    geri konur; boylece ic ice kodlar da acilir.
    """
    result = text
    for ph in sorted(replacements, key=lambda kod: int(kod[4:8]), reverse=True):
        result = result.replace(ph, replacements[ph])
    return result


# ============================================================
# Dogrulama esikleri (spec 9.2, A3 plani netlestirme 3-7).
# Saglayici yanit verdi ama sonuc guvenilmezse metin orijinal kalir ve kayit
# needs_translation ile isaretlenir; yeniden deneme ve devre kesici UYGULANMAZ.
# ============================================================
MIN_RATIO = float(os.environ.get('TRANSLATE_MIN_RATIO', '0.4'))
# 'Kubernetes 1.31', 'CVE-2026-1234' gibi kisa metinler mesru olarak ayni kalir
ECHO_MIN_WORDS = 4
# Kisa metinlerin Turkce karsiligi mesru olarak cok kisa olabilir
TRUNCATION_MIN_CHARS = 80


def _normalize_for_echo(text: str) -> str:
    return re.sub(r'\s+', ' ', text).strip().casefold()


def _translatable_word_count(protected: str) -> int:
    """Yer tutucular cikarildiktan sonra kalan, en az iki harfli kelime sayisi."""
    return len(re.findall(r'[^\W\d_]{2,}', _PLACEHOLDER_RE.sub(' ', protected)))


def verify_translation(protected: str, translated: str,
                       placeholders: Iterable[str]) -> Optional[str]:
    """Saglayici cevabinin guvenilir olup olmadigini soyler.

    protected: Saglayiciya gonderilen, terimleri korunmus metin.
    translated: Onarilmis ama henuz geri konmamis saglayici cevabi.
    placeholders: Bu cagrinin urettigi kodlar. Metinde bunlarin disinda kod
    olabilir (k8s_scraper dis katmani); onlar burada denetlenmez.

    Sorun yoksa None, varsa kisa bir sebep dondurur.
    """
    eksik = [kod for kod in placeholders if kod not in translated]
    if eksik:
        return f'eksik yer tutucu ({len(eksik)})'
    if (_normalize_for_echo(translated) == _normalize_for_echo(protected)
            and _translatable_word_count(protected) >= ECHO_MIN_WORDS):
        return 'yanki'
    if len(protected) >= TRUNCATION_MIN_CHARS and len(translated) < MIN_RATIO * len(protected):
        return 'kirpilma'
    return None


class _LocalGate:
    """Tek process icin hiz siniri + cooldown (Redis/Django yoksa kullanilir)."""

    def __init__(self):
        self._next_slot = 0.0
        self._cooldown_until = 0.0

    def wait_for_slot(self, interval: float) -> None:
        wait = self._next_slot - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        self._next_slot = time.monotonic() + interval

    def cooldown_active(self) -> bool:
        return time.monotonic() < self._cooldown_until

    def start_cooldown(self, seconds: float) -> None:
        self._cooldown_until = time.monotonic() + seconds


class _RedisGate:
    """Tum worker process'lerinin paylastigi hiz siniri + cooldown."""

    def __init__(self, client, prefix: str = 'translate'):
        self.client = client
        self.slot_key = f'{prefix}:slot'
        self.cooldown_key = f'{prefix}:cooldown'

    def wait_for_slot(self, interval: float) -> None:
        interval_ms = max(int(interval * 1000), 1)
        # Anahtar duruyorsa baska bir process az once istek yapti; suresi dolana kadar bekle
        while not self.client.set(self.slot_key, 1, nx=True, px=interval_ms):
            time.sleep(max(self.client.pttl(self.slot_key), 50) / 1000)

    def cooldown_active(self) -> bool:
        return bool(self.client.exists(self.cooldown_key))

    def start_cooldown(self, seconds: float) -> None:
        if seconds > 0:
            self.client.set(self.cooldown_key, 1, px=int(seconds * 1000))
        else:
            self.client.delete(self.cooldown_key)


_failure_count = 0


def consume_translation_failures() -> int:
    """
    Son cagridan beri cevrilemeyen parca sayisini dondurur ve sayaci sifirlar.
    Task'lar her kayittan sonra cagirir; > 0 ise kayit `needs_translation` olur.
    """
    global _failure_count
    count, _failure_count = _failure_count, 0
    return count


# ------------------------------------------------------------
# Saglayici zinciri (spec 2026-09-14-ceviri-saglayici-zinciri)
# ------------------------------------------------------------
# translate_text saglayicilari translation_providers.SAGLAYICILAR sirasiyla
# dener: LibreTranslate -> orijinal metin (Gemini yalniz retranslate'te).

_used_providers: Set[str] = set()


def consume_translation_providers() -> Set[str]:
    """Son cagridan beri basariyla kullanilan saglayici adlarini dondurur ve sifirlar."""
    global _used_providers
    kullanilan, _used_providers = _used_providers, set()
    return kullanilan


def kayit_saglayicisi(kullanilanlar: Iterable[str]) -> str:
    """Kaydin saglayicisi: en dusuk kaliteli parca belirleyicidir."""
    kullanilanlar = set(kullanilanlar)
    if 'libretranslate' in kullanilanlar:
        return 'libretranslate'
    if 'google' in kullanilanlar:
        return 'google'
    return ''


def saglayicilar() -> list:
    from . import translation_providers as tp
    return list(tp.SAGLAYICILAR)


def herhangi_saglayici_hazir() -> bool:
    return any(s.available() for s in saglayicilar())


def translate_text(text: str) -> str:
    """
    Tek bir metin parcasini Turkce'ye cevirir.
    Terim koruma uygulanir. Saglayicilar sirayla denenir (bkz. saglayicilar());
    her denemenin cevabi onarilir, dogrulanir (verify_translation) ve geri konur.
    Guvenilir ceviri ureten ilk saglayicinin sonucu doner ve adi
    consume_translation_providers ile okunur. Hicbiri basarili olmazsa orijinal
    metin doner ve basarisizlik sayaci artar (bkz. consume_translation_failures).
    """
    global _failure_count
    if not text or len(text.strip()) == 0:
        return ""

    try:
        protected, replacements = _protect_terms(text)
    except Exception as e:
        print(f"  [Ceviri] Hata: {e}")
        _failure_count += 1
        return text

    for saglayici in saglayicilar():
        if not saglayici.available():
            continue
        try:
            translated = saglayici.translate(protected)
            if translated is None:
                continue
            # Saglayici yer tutucuyu 'xtrm 0001x' gibi bozabilir; geri koymadan ONCE onarilmali
            translated = _repair_placeholders(translated)
            sorun = verify_translation(protected, translated, replacements)
            if sorun is None:
                restored = _restore_terms(translated, replacements)
                if any(kod in restored for kod in replacements):
                    sorun = 'yer tutucu kalintisi'
            if sorun:
                print(f"  [Ceviri] {saglayici.name} dogrulama basarisiz ({sorun}).")
                continue
            sonuc = turkish_post_process(restored)
        except Exception as e:
            print(f"  [Ceviri] {saglayici.name} hata: {e}")
            continue
        _used_providers.add(saglayici.name)
        return sonuc

    _failure_count += 1
    return text


def translate_long_text(text: str, chunk_size: int = 4500) -> str:
    """
    Uzun metinleri cumle bazli parcalara bolup cevirir.
    Her parca icin terim koruma + post-processing uygulanir.
    """
    if not text or len(text.strip()) == 0:
        return ""

    if len(text) <= chunk_size:
        return translate_text(text)

    # Cumle sinirlarindan bol
    sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks: List[str] = []
    current_chunk = ""

    for sentence in sentences:
        if len(current_chunk) + len(sentence) + 1 <= chunk_size:
            current_chunk += (" " + sentence) if current_chunk else sentence
        else:
            if current_chunk:
                chunks.append(current_chunk)
            # Eger tek cumle chunk_size'dan buyukse, parcala
            if len(sentence) > chunk_size:
                # Satir sonlarindan bol
                sub_parts = sentence.split('\n')
                sub_chunk = ""
                for part in sub_parts:
                    if len(sub_chunk) + len(part) + 1 <= chunk_size:
                        sub_chunk += ("\n" + part) if sub_chunk else part
                    else:
                        if sub_chunk:
                            chunks.append(sub_chunk)
                        sub_chunk = part
                current_chunk = sub_chunk
            else:
                current_chunk = sentence

    if current_chunk:
        chunks.append(current_chunk)

    translated_parts: List[str] = []
    for i, chunk in enumerate(chunks):
        try:
            translated = translate_text(chunk)
            translated_parts.append(translated)
        except Exception as e:
            print(f"  [Ceviri] Chunk {i+1}/{len(chunks)} hatasi: {e}")
            translated_parts.append(chunk)

    result = ' '.join(translated_parts)
    # Post-process: chunk birlestirme sonrasi olusan sorunlari duzelt
    # (translate_text zaten her chunk icin post-process yapar,
    # ama birlestirme yeni sorunlar olusturabilir)
    return turkish_post_process(result)


# ============================================================
# 4. TURKCE POST-PROCESSING
# ============================================================
# Ceviri sonrasi Turkce imla kurallarina uyum duzeltmeleri.
# ============================================================

# Saglayicilarin sik yaptigi hatali ceviriler
# Format: (regex_pattern, replacement_string)
TRANSLATION_FIXES = [
    # --- Yanlis cevrilmis teknik kavramlar ---
    (r'\bKabuk\b', 'Shell'),
    (r'\bkabuk\b', 'shell'),
    (r'\byığın\b', 'stack'),
    (r'\bYığın\b', 'Stack'),
    (r'\bağ geçidi\b', 'gateway'),
    (r'\bAğ geçidi\b', 'Gateway'),
    (r'\bişlem hattı\b', 'pipeline'),
    (r'\bİşlem hattı\b', 'Pipeline'),
    (r'\bgörev\b', 'task'),  # "görev" genellikle "task" olmali teknik baglamda
    (r'\bdepo\b', 'repository'),  # "depo" -> repo
    (r'\bDepo\b', 'Repository'),
    (r'\btaahhüt\b', 'commit'),
    (r'\bTaahhüt\b', 'Commit'),
    (r'\bdallanma\b', 'branch'),
    (r'\bDallanma\b', 'Branch'),
    (r'\bbirleştirme\b', 'merge'),
    (r'\bBirleştirme\b', 'Merge'),
]

# Turkce karakter eslemeleri — yanlis encode durumunda
TURKISH_CHAR_FIXES = {
    'Ä±': 'ı',  # ı
    'Ã¶': 'ö',  # ö
    'Ã¼': 'ü',  # ü
    'ÅŸ': 'ş',  # ş
    'Ã§': 'ç',  # ç
    'ÄŸ': 'ğ',  # ğ
    'Ä°': 'İ',  # İ
}


def turkish_post_process(text: str) -> str:
    """
    Turkce ceviri sonrasi imla ve format duzeltmeleri.
    URL'ler, email adresleri ve surum numaralari post-processing'den korunur.
    """
    if not text:
        return text

    result = text

    # --- 0. URL'leri, email'leri ve surum numaralarini koru ---
    # Post-processing kurallari nokta/virgul etrafinda degisiklik yaptigindan
    # URL'lerdeki noktalari bozabilir. Oncelikle bunlari placeholder'la degistir.
    _pp_replacements: Dict[str, str] = {}
    _pp_counter = [0]

    def _pp_protect(m):
        _pp_counter[0] += 1
        ph = f"XPPX{_pp_counter[0]:04d}XPPX"
        _pp_replacements[ph] = m.group(0)
        return ph

    # URL'leri koru
    result = re.sub(r'https?://\S+', _pp_protect, result)
    # Email adreslerini koru
    result = re.sub(r'\S+@\S+\.\S+', _pp_protect, result)
    # Surum numaralarini koru (v1.2.3, 8.19.12, 25.0.2+10)
    result = re.sub(r'\bv?\d+\.\d+(?:\.\d+)*(?:[+\-][\w.]+)?\b', _pp_protect, result)
    # Dosya uzantilari (.html, .json, .yaml vs.)
    result = re.sub(r'\.\w{2,5}\b', _pp_protect, result)

    # --- 1. Bozuk placeholder'lari onar ---
    result = re.sub(r'[Xx]\s*[Tt]\s*[Rr]\s*[Mm]\s*(\d{4})\s*[Xx]', r'XTRM\1X', result)

    # --- 2. Bozuk Turkce karakter encoding'leri onar ---
    for wrong, correct in TURKISH_CHAR_FIXES.items():
        result = result.replace(wrong, correct)

    # --- 3. Noktalama duzeltmeleri ---
    # Noktadan/virgulden once bosluk olmamali
    result = re.sub(r'\s+([.,;:!?)])', r'\1', result)
    # Noktadan/virgulden sonra bosluk olmali (harf geliyorsa)
    result = re.sub(r'([.,;:!?])([A-Za-zÀ-ÿĞğİıÖöÜüŞşÇç])', r'\1 \2', result)
    # Parantez duzeltmeleri
    result = re.sub(r'\(\s+', '(', result)
    result = re.sub(r'\s+\)', ')', result)

    # --- 4. Coklu bosluk ve satir sonu temizligi ---
    result = re.sub(r'[ \t]+', ' ', result)
    result = re.sub(r' *\n *', '\n', result)
    result = re.sub(r'\n{3,}', '\n\n', result)

    # --- 5. Cumle basi buyuk harf ---
    def _capitalize_after_period(m):
        return m.group(1) + m.group(2).upper()
    result = re.sub(r'([.!?]\s+)([a-zğüşöçıi])', _capitalize_after_period, result)

    # Metnin ilk harfini buyut
    if result and result[0].islower():
        result = result[0].upper() + result[1:]

    # Satir baslarinda buyuk harf
    def _capitalize_line_start(m):
        return m.group(1) + m.group(2).upper()
    result = re.sub(r'(\n)([a-zğüşöçıi])', _capitalize_line_start, result)

    # --- 6. Tarih formati duzeltmeleri ---
    EN_TO_TR_MONTHS = {
        'January': 'Ocak', 'February': 'Şubat', 'March': 'Mart',
        'April': 'Nisan', 'May': 'Mayıs', 'June': 'Haziran',
        'July': 'Temmuz', 'August': 'Ağustos', 'September': 'Eylül',
        'October': 'Ekim', 'November': 'Kasım', 'December': 'Aralık',
    }
    for en_month, tr_month in EN_TO_TR_MONTHS.items():
        result = re.sub(r'\b' + en_month + r'\b', tr_month, result)

    # --- 7. "K8s" kisaltmasini koru ---
    result = re.sub(r'\bK\s*8\s*s\b', 'K8s', result)
    result = re.sub(r'\bk\s*8\s*s\b', 'K8s', result)

    # --- 8. Korunan URL/surum/dosya uzantilarini geri koy ---
    for ph in sorted(_pp_replacements.keys(), key=len, reverse=True):
        result = result.replace(ph, _pp_replacements[ph])

    return result.strip()


# ============================================================
# 5. K8s ICIN OZEL: Yapilandirilmis CHANGELOG cevirisi
# ============================================================

def translate_structured_changelog(text: str) -> str:
    """
    Kubernetes CHANGELOG gibi yapilandirilmis metinleri cevirir.
    Her madde (- ile baslayan satir) ayri ayri cevirilir.
    Basliklar (### ile baslayan) cevirilmez.
    """
    if not text:
        return ""

    lines = text.split('\n')
    translated_lines: List[str] = []

    for line in lines:
        stripped = line.strip()

        # Bos satir
        if not stripped:
            translated_lines.append('')
            continue

        # Basliklar (### Features, ### Bug Fixes, vs.)
        if stripped.startswith('#'):
            # Baslik metnini cevir ama # isaretlerini koru
            hashes = re.match(r'^(#+\s*)', stripped)
            if hashes:
                prefix = hashes.group(1)
                title_text = stripped[len(prefix):]
                try:
                    translated_title = translate_text(title_text)
                    translated_lines.append(prefix + translated_title)
                except Exception:
                    translated_lines.append(stripped)
            else:
                translated_lines.append(stripped)
            continue

        # Liste ogeleri (- ile baslayan)
        if stripped.startswith('- ') or stripped.startswith('* '):
            bullet = stripped[0]  # - veya *
            item_text = stripped[2:]
            try:
                translated_item = translate_text(item_text)
                translated_lines.append(f'{bullet} {translated_item}')
            except Exception:
                translated_lines.append(stripped)
            continue

        # Diger satirlar — normal cevir
        try:
            translated_lines.append(translate_text(stripped))
        except Exception:
            translated_lines.append(stripped)

    result = '\n'.join(translated_lines)
    return turkish_post_process(result)
