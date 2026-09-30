import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  ImageBackground,
  Modal,
  Platform,
  Pressable,
  SafeAreaView,
  ScrollView,
  StatusBar,
  StyleSheet,
  Switch,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import { StatusBar as ExpoStatusBar } from 'expo-status-bar';
import { Audio } from 'expo-av';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { Headphones, History, House, User } from 'lucide-react-native';
import Svg, { Circle, Defs, Line, LinearGradient, Path, Stop, Text as SvgText } from 'react-native-svg';

const DEFAULT_API_BASE_URL = Platform.OS === 'android'
  ? 'http://10.0.2.2:8000/api/v1'
  : 'http://127.0.0.1:8000/api/v1';
const API_BASE_URL = (process.env.EXPO_PUBLIC_API_BASE_URL || DEFAULT_API_BASE_URL).replace(/\/$/, '');
const ACCESS_TOKEN_KEY = '@jipangi/access-token';
const REFRESH_TOKEN_KEY = '@jipangi/refresh-token';
const HISTORY_KEY = '@jipangi/history';
const MICROPHONE_PERMISSION_KEY = '@jipangi/microphone-permission-granted';
const VOCAL_TRACT_BACKGROUND_IMAGE = {
  uri: 'https://upload.wikimedia.org/wikipedia/commons/thumb/3/39/Neutral_Sagittal_Section.svg/960px-Neutral_Sagittal_Section.svg.png',
};
const COLORS = { ink: '#1E2440', muted: '#687089', primary: '#4F46E5', soft: '#EEF0FF', surface: '#FFFFFF', canvas: '#F7F8FC', line: '#E3E6EF', success: '#16835A', danger: '#D84B57', warning: '#A66A00' };
const LEVELS = ['전체', '초급', '중급', '상급', '심화'];
const DIFFICULTY_TO_LABEL = { easy: '초급', normal: '중급', hard: '상급', special: '심화' };
const BASELINE_QUESTIONS = [
  { id: 'repeat_requests', text: '상대방이 내 말을 알아듣지 못해 다시 말해 달라고 하나요?' },
  { id: 'conversation_avoidance', text: '발음 때문에 대화나 발표를 피하게 되나요?' },
  { id: 'long_sentence_difficulty', text: '긴 문장을 말할수록 발음이 흐려지거나 어려워지나요?' },
  { id: 'speaking_fatigue', text: '말을 오래 하면 입이나 목이 쉽게 피로해지나요?' },
  { id: 'phone_difficulty', text: '전화 통화에서 말이 잘 전달되지 않는다고 느끼나요?' },
];
const BASELINE_OPTIONS = [
  { value: 0, label: '전혀 없음' },
  { value: 1, label: '드물게' },
  { value: 2, label: '가끔' },
  { value: 3, label: '자주' },
  { value: 4, label: '매우 자주' },
];
const ERROR_FIELD_LABELS = {
  username: '아이디',
  password: '비밀번호',
  age: '연령',
  phone_number: '전화번호',
  answers: '평가 응답',
};
const HANGUL_ONSET_TO_IPA = [['k'], ['k͈'], ['n'], ['t'], ['t͈'], ['ɾ'], ['m'], ['p'], ['p͈'], ['s'], ['s͈'], [], ['tɕ'], ['tɕ͈'], ['tɕʰ'], ['kʰ'], ['tʰ'], ['pʰ'], ['h']];
const HANGUL_VOWEL_TO_IPA = [['a'], ['e'], ['j', 'a'], ['j', 'e'], ['ʌ'], ['e'], ['j', 'ʌ'], ['j', 'e'], ['o'], ['w', 'a'], ['w', 'e'], ['w', 'e'], ['j', 'o'], ['u'], ['w', 'ʌ'], ['w', 'e'], ['w', 'i'], ['j', 'u'], ['ɯ'], ['ɯ', 'i'], ['i']];
const HANGUL_CODA_TO_IPA = [[], ['k̚'], ['k̚'], ['k̚'], ['n'], ['n'], ['n'], ['t̚'], ['l'], ['k̚'], ['m'], ['l'], ['l'], ['l'], ['p̚'], ['l'], ['m'], ['p̚'], ['p̚'], ['t̚'], ['t̚'], ['ŋ'], ['t̚'], ['t̚'], ['k̚'], ['t̚'], ['p̚'], ['t̚']];
const PALATAL_VOWEL_INDEXES = new Set([20, 2, 3, 6, 7, 12, 17]);
const TONGUE_PATHS = {
  neutral: 'M58 151 C94 139 142 135 181 141 C216 148 247 153 279 152',
  bilabial: 'M58 154 C97 146 139 141 180 145 C217 150 248 154 280 153',
  dentalAlveolar: 'M58 154 C85 130 111 105 143 99 C181 100 215 132 279 152',
  alveolarFricative: 'M58 154 C87 133 114 112 148 107 C185 108 219 134 279 152',
  alveoloPalatal: 'M58 155 C94 139 126 111 158 96 C194 80 232 119 280 152',
  velar: 'M58 156 C101 151 149 137 193 103 C224 80 256 121 281 152',
  glottal: 'M58 154 C103 147 149 141 190 145 C225 149 253 153 281 153',
  highFront: 'M58 155 C93 132 130 105 178 100 C217 101 248 134 281 153',
  midFront: 'M58 156 C96 143 137 127 181 128 C223 130 251 146 280 153',
  midBack: 'M58 156 C98 150 143 139 189 130 C228 123 257 143 281 153',
  highBack: 'M58 156 C99 151 145 139 194 116 C232 100 259 128 281 153',
  low: 'M58 158 C96 160 138 158 182 159 C221 159 251 158 281 156',
};
const ARTICULATION_PROFILES = {
  default: { label: '기본 혀 위치', diagramKey: 'neutral', highlight: [178, 130], placeLabel: '중립', description: '이 음소의 세부 조음 정보가 아직 부족해 기본 혀 위치로 표시합니다.' },
  p: { label: '양순 파열음', diagramKey: 'bilabial', highlight: [48, 115], placeLabel: '두 입술', description: '두 입술을 붙였다가 떼며 소리를 냅니다. 혀 자체보다 입술 닫힘이 핵심입니다.' },
  'p͈': { label: '된 양순 파열음', diagramKey: 'bilabial', highlight: [48, 115], placeLabel: '입술 긴장', description: '입술을 단단히 닫고 긴장을 실어 짧고 선명하게 냅니다. 혀모양 차이보다는 긴장도가 중요합니다.' },
  'pʰ': { label: '거센 양순 파열음', diagramKey: 'bilabial', highlight: [48, 115], placeLabel: '입술+숨', description: '입술을 떼는 순간 숨을 더 분명히 내보냅니다. 다이어그램에는 숨의 세기 차이를 간단히 표시합니다.' },
  'p̚': { label: '양순 불파음/받침', diagramKey: 'bilabial', highlight: [48, 115], placeLabel: '입술 닫힘', description: '입술을 닫아 소리를 마무리하고, 영어 p처럼 크게 터뜨리지 않습니다.' },
  m: { label: '양순 비음', diagramKey: 'bilabial', highlight: [48, 115], placeLabel: '입술+코울림', description: '두 입술을 닫고 코로 울림을 보내며 소리를 냅니다.' },
  t: { label: '치경 파열음', diagramKey: 'dentalAlveolar', highlight: [140, 96], placeLabel: '윗잇몸', description: '혀끝이나 혀날을 윗니 뒤쪽의 윗잇몸 부근에 붙였다가 떼며 소리를 냅니다.' },
  't͈': { label: '된 치경 파열음', diagramKey: 'dentalAlveolar', highlight: [140, 96], placeLabel: '윗잇몸 긴장', description: '혀끝/혀날 위치는 치경 파열음과 비슷하지만, 더 단단한 긴장으로 짧고 선명하게 냅니다.' },
  'tʰ': { label: '거센 치경 파열음', diagramKey: 'dentalAlveolar', highlight: [140, 96], placeLabel: '윗잇몸+숨', description: '혀끝/혀날을 떼는 순간 숨을 더 강하게 내보냅니다.' },
  't̚': { label: '치경 불파음/받침', diagramKey: 'dentalAlveolar', highlight: [140, 96], placeLabel: '윗잇몸 닫힘', description: '혀끝/혀날을 윗잇몸 쪽에 붙여 소리를 닫고, 끝에서 터뜨리지 않습니다.' },
  n: { label: '치경 비음', diagramKey: 'dentalAlveolar', highlight: [140, 96], placeLabel: '윗잇몸+코울림', description: '혀끝/혀날을 윗잇몸에 대고 코로 울림을 보냅니다.' },
  l: { label: '치경 설측음', diagramKey: 'dentalAlveolar', highlight: [140, 96], placeLabel: '혀 옆길', description: '혀끝을 윗잇몸에 대고 혀 옆으로 공기가 빠져나가게 합니다.' },
  'ɾ': { label: '치경 탄음', diagramKey: 'dentalAlveolar', highlight: [140, 96], placeLabel: '혀끝 튕김', description: '혀끝을 윗잇몸 근처에 아주 짧게 튕기듯 닿게 합니다.' },
  s: { label: '치경 마찰음', diagramKey: 'alveolarFricative', highlight: [147, 104], placeLabel: '좁은 틈', description: '혀끝/혀날을 윗잇몸 가까이에 두되 완전히 막지 않고, 좁은 틈으로 공기를 지나가게 합니다.' },
  's͈': { label: '된 치경 마찰음', diagramKey: 'alveolarFricative', highlight: [147, 104], placeLabel: '강한 마찰', description: '혀 앞쪽의 좁은 틈과 긴장을 더 분명히 만들어 선명한 마찰을 냅니다.' },
  'ɕ': { label: '치경구개 마찰음', diagramKey: 'alveoloPalatal', highlight: [160, 95], placeLabel: '혀 앞쪽', description: '혀 앞쪽을 윗잇몸 뒤쪽~입천장 앞쪽으로 올려 부드러운 마찰을 만듭니다.' },
  'ɕ͈': { label: '된 치경구개 마찰음', diagramKey: 'alveoloPalatal', highlight: [160, 95], placeLabel: '혀 앞쪽 긴장', description: '혀 앞쪽을 더 긴장시켜 입천장 앞쪽 가까이에서 선명한 마찰을 만듭니다.' },
  'tɕ': { label: '치경구개 파찰음', diagramKey: 'alveoloPalatal', highlight: [160, 95], placeLabel: '윗잇몸 뒤~입천장 앞', description: '혀 앞부분을 윗잇몸 뒤쪽에서 입천장 앞쪽 사이로 올려 잠깐 막은 뒤 마찰을 만듭니다.' },
  'tɕ͈': { label: '된 치경구개 파찰음', diagramKey: 'alveoloPalatal', highlight: [160, 95], placeLabel: '앞쪽 긴장', description: '혀 앞부분 위치는 비슷하지만 더 긴장된 상태로 짧고 선명한 파찰음을 만듭니다.' },
  'tɕʰ': { label: '거센 치경구개 파찰음', diagramKey: 'alveoloPalatal', highlight: [160, 95], placeLabel: '앞쪽+숨', description: '혀 앞부분으로 막힘과 마찰을 만든 뒤 숨을 더 강하게 내보냅니다.' },
  k: { label: '연구개 파열음', diagramKey: 'velar', highlight: [203, 99], placeLabel: '입천장 뒤쪽', description: '혀 뒤쪽을 입천장 뒤쪽, 즉 연구개 쪽에 붙였다가 떼며 소리를 냅니다.' },
  'k͈': { label: '된 연구개 파열음', diagramKey: 'velar', highlight: [203, 99], placeLabel: '뒤쪽 긴장', description: '혀 뒤쪽 위치는 연구개 파열음과 비슷하지만, 더 단단한 긴장으로 짧고 선명하게 냅니다.' },
  'kʰ': { label: '거센 연구개 파열음', diagramKey: 'velar', highlight: [203, 99], placeLabel: '뒤쪽+숨', description: '혀 뒤쪽을 떼는 순간 숨을 더 강하게 내보냅니다.' },
  'k̚': { label: '연구개 불파음/받침', diagramKey: 'velar', highlight: [203, 99], placeLabel: '뒤쪽 닫힘', description: '혀 뒤쪽을 연구개에 붙여 소리를 닫고, 끝에서 크게 터뜨리지 않습니다.' },
  ŋ: { label: '연구개 비음', diagramKey: 'velar', highlight: [203, 99], placeLabel: '뒤쪽+코울림', description: '혀 뒤쪽을 연구개 쪽에 올리고 코로 울림을 보내며 소리를 냅니다.' },
  h: { label: '성문 마찰음', diagramKey: 'glottal', highlight: [267, 132], placeLabel: '목 안쪽', description: '입안의 특정 혀 접촉보다 목 안쪽, 성문 부근에서 숨이 지나가며 마찰이 생깁니다.' },
  i: { label: '전설 고모음', diagramKey: 'highFront', highlight: [173, 101], placeLabel: '앞·위', description: '혀를 앞쪽과 위쪽으로 올리고 입을 많이 벌리지 않습니다. 입술은 둥글게 모으지 않습니다.' },
  e: { label: '전설 중모음', diagramKey: 'midFront', highlight: [169, 126], placeLabel: '앞·중간', description: '혀를 앞쪽 중간 높이에 두고 편안하게 냅니다. 현대 한국어에서는 ㅔ/ㅐ가 비슷하게 실현될 수 있습니다.' },
  a: { label: '저모음', diagramKey: 'low', highlight: [166, 155], placeLabel: '낮게', description: '입을 열고 혀를 낮게 내려 소리를 냅니다.' },
  'ʌ': { label: '후설 중저모음', diagramKey: 'midBack', highlight: [197, 132], placeLabel: '뒤·중간', description: '혀를 약간 뒤쪽 중간 높이에 두고 입을 자연스럽게 엽니다.' },
  o: { label: '후설 중고모음', diagramKey: 'highBack', highlight: [205, 116], placeLabel: '뒤·위+둥근 입술', description: '혀 뒤쪽을 올리고 입술을 둥글게 모읍니다.' },
  u: { label: '후설 고모음', diagramKey: 'highBack', highlight: [211, 108], placeLabel: '뒤·위+둥근 입술', description: '혀 뒤쪽을 높게 올리고 입술을 둥글게 모읍니다.' },
  'ɯ': { label: '후설 고모음', diagramKey: 'highBack', highlight: [199, 113], placeLabel: '뒤·위', description: '혀 뒤쪽을 높게 올리지만 입술은 둥글게 모으지 않습니다.' },
  j: { label: '전설 접근음', diagramKey: 'highFront', highlight: [171, 101], placeLabel: '앞·위 이동', description: 'ㅣ에 가까운 혀 위치에서 다음 모음으로 미끄러지듯 연결합니다.' },
  w: { label: '양순-연구개 접근음', diagramKey: 'highBack', highlight: [207, 110], placeLabel: '뒤쪽+입술 이동', description: '혀 뒤쪽을 올리고 입술을 둥글게 하며 다음 모음으로 연결합니다.' },
};
const ARTICULATION_ALIASES = {
  b: 'p', β: 'p', d: 't', 'ð': 't', ɡ: 'k', g: 'k', ɦ: 'h',
  't͡ɕ': 'tɕ', 't͡ɕ͈': 'tɕ͈', 't͡ɕʰ': 'tɕʰ', dʑ: 'tɕ', 'd͡ʑ': 'tɕ', ʥ: 'tɕ',
  z: 's', ʃ: 'ɕ', ʒ: 'ɕ', 'ʂ': 's', 'ɕʰ': 'tɕʰ',
  r: 'ɾ', 'ɹ': 'ɾ', 'ɫ': 'l',
  'ɪ': 'i', y: 'i', 'ɛ': 'e', æ: 'e', 'ə': 'ʌ', 'ɜ': 'ʌ', 'ɑ': 'a', 'ɔ': 'o', 'ʊ': 'u', 'ɨ': 'ɯ',
};
const ARTICULATION_REFERENCES = [
  { title: 'Neutral Sagittal Section, Wikimedia Commons', detail: 'CC0/Public Domain vocal-tract sagittal section used as the visual base' },
  { title: 'International Phonetic Association', detail: 'Official IPA Chart: consonant place/manner and vowel height/backness criteria' },
  { title: '국립국어원 표준 발음법', detail: '한국어 받침, 연음, 비음화, 구개음화 등 표준 발음 규칙 기준' },
  { title: 'The Handbook of Korean Linguistics, Wiley-Blackwell', detail: 'Korean phonetics/phonology descriptions for consonants and vowels' },
  { title: 'Cambridge University Press: Korean phonology & phonetics', detail: '한국어 조음 위치와 음운 현상에 대한 학술적 설명 참고' },
];

const demoSentences = [
  { id: 1, text: '발음은 부담이 되지 않습니다.', target_ipa: '/p a r ɯ m ɯ n p u d a m i t w e j i a n s ɯ m n i d a/', level: '초급', category: '받침', recommendation_reason: '받침 연습을 시작해 보세요.' },
  { id: 2, text: '비가 오는 날에는 우산이 필요해요.', target_ipa: '/p i k a o n ɯ n n a r e n ɯ n u s a n i p i r j o h e j o/', level: '초급', category: '연음' },
  { id: 3, text: '나는 맛있는 밥을 먹어요.', target_ipa: '/n a n ɯ n m a s i n n ɯ n p a p ɯ r m ʌ g ʌ j o/', level: '중급', category: '비음화' },
];

function normalizeSentence(item) {
  const difficulty = item.difficulty || item.level || 'easy';
  return {
    id: item.id,
    text: item.text || item.sentence || '',
    target_ipa: item.target_ipa || item.ipa || [],
    word_spans: Array.isArray(item.word_spans) ? item.word_spans : [],
    level: DIFFICULTY_TO_LABEL[difficulty] || difficulty,
    category: item.category?.name || item.category || item.type || '기타',
    categoryCode: item.category?.code || '',
    isCustom: !!(item.is_custom || item.created_by || item.category?.code === 'custom-sentences'),
    recommendation_reason: item.recommendation_reason || item.reason || '',
  };
}

async function request(path, { method = 'GET', token, body, form } = {}) {
  const headers = { Accept: 'application/json' };
  if (token) headers.Authorization = `Bearer ${token}`;
  if (body) headers['Content-Type'] = 'application/json';
  const response = await fetch(`${API_BASE_URL}${path}`, { method, headers, body: body ? JSON.stringify(body) : form });
  if (response.status === 204) return null;
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const validationMessage = formatValidationDetails(data.error?.details);
    const error = new Error(validationMessage || data.error?.message || data.detail || data.message || `요청에 실패했습니다. (${response.status})`);
    error.status = response.status;
    error.code = data.error?.code;
    throw error;
  }
  return data;
}

function formatValidationDetails(details) {
  if (!details || typeof details !== 'object') return '';
  return Object.entries(details).flatMap(([field, messages]) => {
    const label = ERROR_FIELD_LABELS[field] || field;
    if (Array.isArray(messages)) return messages.map((message) => `${label}: ${message}`);
    if (messages && typeof messages === 'object') {
      return Object.values(messages).flat().map((message) => `${label}: ${message}`);
    }
    return [`${label}: ${messages}`];
  }).join('\n');
}

function useTransientToast() {
  const [message, setMessage] = useState('');
  const timer = useRef(null);
  useEffect(() => () => clearTimeout(timer.current), []);
  const show = (nextMessage) => {
    clearTimeout(timer.current);
    setMessage(nextMessage);
    timer.current = setTimeout(() => setMessage(''), 1000);
  };
  return { message, show };
}

function TopToast({ message }) {
  if (!message) return null;
  return <View pointerEvents="none" style={styles.toastLayer}><View style={styles.toast}><Text style={styles.toastText}>{message}</Text></View></View>;
}

const wait = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds));

function toneWavDataUri(frequency, durationMs) {
  const sampleRate = 22050;
  const sampleCount = Math.floor((durationMs / 1000) * sampleRate);
  const bytes = new Uint8Array(44 + sampleCount * 2);
  const view = new DataView(bytes.buffer);
  const writeString = (offset, value) => {
    for (let index = 0; index < value.length; index += 1) bytes[offset + index] = value.charCodeAt(index);
  };
  writeString(0, 'RIFF');
  view.setUint32(4, 36 + sampleCount * 2, true);
  writeString(8, 'WAVE');
  writeString(12, 'fmt ');
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeString(36, 'data');
  view.setUint32(40, sampleCount * 2, true);
  for (let index = 0; index < sampleCount; index += 1) {
    const progress = index / sampleCount;
    const envelope = Math.min(1, progress * 16) * Math.max(0, 1 - progress);
    const sample = Math.sin((2 * Math.PI * frequency * index) / sampleRate) * envelope * 0.55;
    view.setInt16(44 + index * 2, Math.floor(sample * 32767), true);
  }
  if (typeof btoa !== 'function') return '';
  let binary = '';
  const chunkSize = 0x8000;
  for (let index = 0; index < bytes.length; index += chunkSize) {
    binary += String.fromCharCode(...bytes.subarray(index, index + chunkSize));
  }
  return `data:audio/wav;base64,${btoa(binary)}`;
}

async function playRecordingCue(kind) {
  const tones = kind === 'stop' ? [{ hz: 740, ms: 90 }, { hz: 980, ms: 120 }] : [{ hz: 880, ms: 130 }];
  try {
    if (Platform.OS === 'web' && typeof window !== 'undefined') {
      const AudioContext = window.AudioContext || window.webkitAudioContext;
      if (!AudioContext) return;
      const context = new AudioContext();
      if (context.state === 'suspended') await context.resume();
      let cursor = context.currentTime + 0.01;
      let totalMs = 0;
      tones.forEach(({ hz, ms }) => {
        const oscillator = context.createOscillator();
        const gain = context.createGain();
        oscillator.type = 'sine';
        oscillator.frequency.value = hz;
        oscillator.connect(gain);
        gain.connect(context.destination);
        gain.gain.setValueAtTime(0.001, cursor);
        gain.gain.exponentialRampToValueAtTime(0.16, cursor + 0.01);
        gain.gain.exponentialRampToValueAtTime(0.001, cursor + ms / 1000);
        oscillator.start(cursor);
        oscillator.stop(cursor + ms / 1000 + 0.02);
        cursor += ms / 1000 + 0.035;
        totalMs += ms + 35;
      });
      await wait(totalMs + 80);
      await context.close().catch(() => {});
      return;
    }
    for (const { hz, ms } of tones) {
      const uri = toneWavDataUri(hz, ms);
      if (!uri) return;
      const { sound } = await Audio.Sound.createAsync({ uri }, { shouldPlay: true, volume: 0.55 });
      await wait(ms + 45);
      await sound.unloadAsync();
    }
  } catch (_) {
    // 녹음 기능 자체가 더 중요하므로, 효과음 실패는 조용히 무시합니다.
  }
}

let microphonePermissionGrantedForSession = false;

async function rememberMicrophonePermission() {
  microphonePermissionGrantedForSession = true;
  try { await AsyncStorage.setItem(MICROPHONE_PERMISSION_KEY, 'true'); } catch (_) {}
}

async function forgetMicrophonePermission() {
  microphonePermissionGrantedForSession = false;
  try { await AsyncStorage.removeItem(MICROPHONE_PERMISSION_KEY); } catch (_) {}
}

async function hasRememberedMicrophonePermission() {
  if (microphonePermissionGrantedForSession) return true;
  try {
    const cached = await AsyncStorage.getItem(MICROPHONE_PERMISSION_KEY);
    if (cached === 'true') {
      microphonePermissionGrantedForSession = true;
      return true;
    }
  } catch (_) {}
  return false;
}

async function ensureMicrophonePermission(reason) {
  const remembered = await hasRememberedMicrophonePermission();
  try {
    const current = await Audio.getPermissionsAsync();
    if (current?.granted) {
      await rememberMicrophonePermission();
      return true;
    }
    if (current?.status === 'denied' && current?.canAskAgain === false) {
      await forgetMicrophonePermission();
      Alert.alert('마이크 권한 필요', '브라우저 또는 iPhone 설정에서 이 사이트의 마이크 권한을 허용해 주세요.');
      return false;
    }
    if (remembered) return true;
  } catch (_) {
    // 일부 웹뷰/브라우저에서는 권한 상태 조회가 불안정할 수 있습니다.
    if (remembered) return true;
  }
  const permission = await Audio.requestPermissionsAsync();
  if (permission?.granted) {
    await rememberMicrophonePermission();
    return true;
  }
  Alert.alert('마이크 권한 필요', reason);
  return false;
}

function formatIpa(value) {
  if (Array.isArray(value)) return value.join(' ');
  return String(value || '').replaceAll('/', '').trim();
}

function ipaTokens(value) {
  if (Array.isArray(value)) return value.map((item) => String(item || '').trim()).filter(Boolean);
  return formatIpa(value).split(/\s+/).map((item) => item.trim()).filter(Boolean);
}

function phoneProfile(phone) {
  const normalized = String(phone || '').trim().replace(/͡/g, '');
  const aliased = ARTICULATION_ALIASES[normalized] || normalized;
  return ARTICULATION_PROFILES[aliased] || ARTICULATION_PROFILES.default;
}

function errorTargetPhone(error) {
  return error?.target_phone || error?.expected_phone || error?.target || '';
}

function errorRecognizedPhone(error) {
  return error?.recognized_phone || error?.actual_phone || error?.user || '';
}

function errorPosition(error) {
  const value = error?.phone_position ?? error?.target_index ?? error?.position ?? error?.user_index;
  return Number.isInteger(value) ? value : null;
}

function ipaWindow(tokens, centerIndex, fallbackPhone) {
  if (centerIndex === null || !tokens.length) return fallbackPhone ? [fallbackPhone] : [];
  const start = Math.max(0, centerIndex - 1);
  const end = Math.min(tokens.length, centerIndex + 2);
  const windowTokens = tokens.slice(start, end);
  return windowTokens.length ? windowTokens : fallbackPhone ? [fallbackPhone] : [];
}

function extensionForAudioType(type, fallback = 'm4a') {
  const mime = String(type || '').split(';')[0].toLowerCase();
  if (mime.includes('webm')) return 'webm';
  if (mime.includes('wav') || mime.includes('wave')) return 'wav';
  if (mime.includes('ogg')) return 'ogg';
  if (mime.includes('mpeg') || mime.includes('mp3')) return 'mp3';
  if (mime.includes('aac')) return 'aac';
  if (mime.includes('mp4') || mime.includes('m4a')) return 'm4a';
  return fallback;
}

function webAudioFileFromBlob(blob, meta, prefix) {
  const mimeType = blob.type || meta?.type || 'audio/mp4';
  const fileName = meta?.name || `${prefix}-${Date.now()}.${extensionForAudioType(mimeType, 'm4a')}`;
  if (typeof File !== 'undefined') {
    return { file: new File([blob], fileName, { type: mimeType }), fileName, mimeType };
  }
  return { file: blob, fileName, mimeType };
}

async function createWebMicrophoneRecording() {
  if (typeof navigator === 'undefined' || !navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') {
    throw new Error('이 브라우저에서는 마이크 녹음을 지원하지 않습니다.');
  }

  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  const supportedTypes = [
    'audio/mp4;codecs=mp4a.40.2',
    'audio/mp4',
    'audio/webm;codecs=opus',
    'audio/webm',
  ];
  const mimeType = supportedTypes.find((type) => MediaRecorder.isTypeSupported?.(type)) || '';
  const recorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
  const chunks = [];
  let blob = null;
  let uri = null;

  recorder.addEventListener('dataavailable', (event) => {
    if (event.data?.size) chunks.push(event.data);
  });
  recorder.start(250);

  return {
    async stopAndUnloadAsync() {
      if (recorder.state !== 'inactive') {
        await new Promise((resolve, reject) => {
          recorder.addEventListener('stop', resolve, { once: true });
          recorder.addEventListener('error', (event) => reject(event.error || new Error('녹음 저장에 실패했습니다.')), { once: true });
          recorder.stop();
        });
      }
      stream.getTracks().forEach((track) => track.stop());
      blob = new Blob(chunks, { type: recorder.mimeType || mimeType || 'audio/webm' });
      uri = URL.createObjectURL(blob);
    },
    getURI() { return uri; },
    getBlobSize() { return blob?.size || 0; },
    getMimeType() { return blob?.type || recorder.mimeType || mimeType || 'audio/webm'; },
  };
}

function hangulCharacterToIpa(character) {
  const code = character.charCodeAt(0) - 0xAC00;
  if (code < 0 || code >= 11172) return character.trim() ? [character] : [];
  const onset = Math.floor(code / 588);
  const vowel = Math.floor((code % 588) / 28);
  const coda = code % 28;
  const phones = [];
  if (onset === 9 && PALATAL_VOWEL_INDEXES.has(vowel)) phones.push('ɕ');
  else if (onset === 10 && PALATAL_VOWEL_INDEXES.has(vowel)) phones.push('ɕ͈');
  else phones.push(...HANGUL_ONSET_TO_IPA[onset]);
  phones.push(...HANGUL_VOWEL_TO_IPA[vowel]);
  phones.push(...HANGUL_CODA_TO_IPA[coda]);
  return phones;
}

function hangulToIpa(text) {
  const phones = [];
  for (const character of String(text || '')) {
    phones.push(...hangulCharacterToIpa(character));
  }
  return phones;
}

function normalizePhoneForMatch(phone) {
  const normalized = String(phone || '').trim().replace(/͡/g, '');
  return ARTICULATION_ALIASES[normalized] || normalized;
}

function phoneMatches(left, right) {
  if (!left || !right) return false;
  return normalizePhoneForMatch(left) === normalizePhoneForMatch(right);
}

function pathNumbers(path) {
  return String(path || '').match(/-?\d+(?:\.\d+)?/g)?.map(Number) || [];
}

function interpolateValue(start, end, progress) {
  return start + (end - start) * progress;
}

function interpolatePath(startPath, endPath, progress) {
  const startNumbers = pathNumbers(startPath);
  const endNumbers = pathNumbers(endPath);
  if (!startNumbers.length || startNumbers.length !== endNumbers.length) return endPath;
  let index = 0;
  return String(startPath).replace(/-?\d+(?:\.\d+)?/g, () => {
    const value = interpolateValue(startNumbers[index], endNumbers[index], progress);
    index += 1;
    return value.toFixed(1).replace(/\.0$/, '');
  });
}

const TONGUE_COMPACT_ORIGIN_X = 48;
const TONGUE_COMPACT_SCALE_X = 0.73;
const TONGUE_OFFSET_X = 14;

function compactTongueX(value) {
  return TONGUE_OFFSET_X + TONGUE_COMPACT_ORIGIN_X + (Number(value) - TONGUE_COMPACT_ORIGIN_X) * TONGUE_COMPACT_SCALE_X;
}

function compactTonguePoint(point) {
  const [x, y] = Array.isArray(point) ? point : ARTICULATION_PROFILES.default.highlight;
  return [compactTongueX(x), y];
}

function compactTonguePath(path) {
  let numberIndex = 0;
  return String(path || '').replace(/-?\d+(?:\.\d+)?/g, (match) => {
    const value = Number(match);
    const next = numberIndex % 2 === 0 ? compactTongueX(value) : value;
    numberIndex += 1;
    return next.toFixed(1).replace(/\.0$/, '');
  });
}

function wordPhoneRanges(word) {
  let cursor = 0;
  return Array.from(String(word || '')).map((character, index) => {
    const phones = hangulCharacterToIpa(character);
    const range = { character, index, start: cursor, end: cursor + phones.length, phones };
    cursor += phones.length;
    return range;
  });
}

function wordSpanForError(error, sentence) {
  const word = String(error?.word || '').trim();
  const wordSpans = Array.isArray(sentence?.word_spans) ? sentence.word_spans : [];
  const wordIndex = Number.isInteger(error?.word_index) ? error.word_index : null;
  return wordSpans.find((item, index) => {
    if (wordIndex !== null) return index === wordIndex;
    return String(item?.word || '').trim() === word;
  }) || null;
}

function highlightIndexesForErrorWord(error, sentence) {
  const word = String(error?.word || '').trim();
  if (!word) return new Set();
  const span = wordSpanForError(error, sentence);
  const phonePosition = errorPosition(error);
  const syllables = Array.isArray(span?.syllables) ? span.syllables : [];
  if (Number.isInteger(phonePosition) && syllables.length) {
    const targetPhone = errorTargetPhone(error);
    const operation = String(error?.operation || error?.error_type || error?.type || '');
    const syllablesWithIndex = syllables
      .map((syllable, index) => ({ syllable, index }))
      .filter(({ syllable }) => Number.isInteger(syllable.start) && Number.isInteger(syllable.end));
    const matched = syllablesWithIndex
      .filter(({ syllable }) => phonePosition >= syllable.start && phonePosition < syllable.end)
      .map(({ index }) => index);
    if (matched.length) {
      const currentIndex = matched[0];
      const current = syllables[currentIndex];
      const next = syllables[currentIndex + 1];
      const currentIpa = Array.isArray(current?.ipa) ? current.ipa : [];
      const nextIpa = Array.isArray(next?.ipa) ? next.ipa : [];
      const isLastPhoneOfCurrentSyllable = phonePosition === current.end - 1;
      const repeatedAtNextSyllable = nextIpa.length && phoneMatches(currentIpa[currentIpa.length - 1], nextIpa[0]) && phoneMatches(targetPhone, nextIpa[0]);
      if (operation === 'deletion' && isLastPhoneOfCurrentSyllable && repeatedAtNextSyllable) {
        return new Set([currentIndex + 1]);
      }
      return new Set(matched);
    }
    const boundaryMatched = syllablesWithIndex
      .filter(({ syllable }) => phonePosition === syllable.end)
      .map(({ index }) => index);
    if (boundaryMatched.length) return new Set([boundaryMatched[boundaryMatched.length - 1]]);
  }
  const ranges = wordPhoneRanges(word);
  const targetPhone = errorTargetPhone(error);
  const exactMatches = ranges.filter((range) => range.phones.some((phone) => phoneMatches(phone, targetPhone)));
  if (exactMatches.length) return new Set([exactMatches[0].index]);
  return new Set(word.length === 1 ? [0] : []);
}

function feedbackUnitForError(error, sentence) {
  const word = String(error?.word || '').trim();
  const highlightIndexes = highlightIndexesForErrorWord(error, sentence);
  const span = wordSpanForError(error, sentence);
  const syllables = Array.isArray(span?.syllables) && span.syllables.length
    ? span.syllables
    : Array.from(word).map((character) => ({ text: character, ipa: hangulCharacterToIpa(character) }));
  const markedIndexes = [...highlightIndexes].sort((a, b) => a - b);
  const unitText = markedIndexes.length
    ? markedIndexes.map((index) => syllables[index]?.text).filter(Boolean).join('')
    : word || errorTargetPhone(error) || '발음';
  const wordIndex = Number.isInteger(error?.word_index) ? error.word_index : 'unknown';
  const unitKey = word
    ? `${wordIndex}:${word}:${markedIndexes.join('-') || 'whole'}`
    : `phone:${error.sequence ?? error.phone_position ?? errorTargetPhone(error)}`;
  return { key: unitKey, unitText, word, highlightIndexes, primaryError: error, errors: [error] };
}

function groupFeedbackErrors(errors, sentence) {
  const groups = new Map();
  for (const error of Array.isArray(errors) ? errors : []) {
    const unit = feedbackUnitForError(error, sentence);
    const existing = groups.get(unit.key);
    if (!existing) {
      groups.set(unit.key, unit);
      continue;
    }
    existing.errors.push(error);
    existing.highlightIndexes = new Set([...existing.highlightIndexes, ...unit.highlightIndexes]);
    if (!existing.primaryError?.specific_feedback && error?.specific_feedback) {
      existing.primaryError = error;
    }
  }
  return [...groups.values()];
}

function normalizeRecord(item) {
  return {
    ...item,
    id: item.analysis_id || item.id,
    sentence: typeof item.sentence === 'string'
      ? { id: item.sentence_id, text: item.sentence }
      : item.sentence,
  };
}

function normalizePhoneNumberInput(value) {
  return String(value || '').replace(/[\s-]/g, '');
}

function App() {
  const [showSplash, setShowSplash] = useState(true);
  const [screen, setScreen] = useState('login');
  const [token, setToken] = useState(null);
  const [refreshToken, setRefreshToken] = useState(null);
  const [sentences, setSentences] = useState(demoSentences);
  const [selected, setSelected] = useState(null);
  const [level, setLevel] = useState('전체');
  const [type, setType] = useState('전체');
  const [loadingSentences, setLoadingSentences] = useState(false);
  const [notice, setNotice] = useState('');
  const [recording, setRecording] = useState(null);
  const [recordingStartedAt, setRecordingStartedAt] = useState(null);
  const [elapsed, setElapsed] = useState(0);
  const [audioUri, setAudioUri] = useState(null);
  const [audioUploadMeta, setAudioUploadMeta] = useState(null);
  const [consentToStore, setConsentToStore] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [result, setResult] = useState(null);
  const [history, setHistory] = useState([]);
  const [dashboard, setDashboard] = useState(null);
  const { message: toast, show: showToast } = useTransientToast();
  const refreshPromise = useRef(null);

  async function resetPracticeState() {
    if (recording) {
      try { await recording.stopAndUnloadAsync(); } catch (_) {}
      try { await Audio.setAudioModeAsync({ allowsRecordingIOS: false }); } catch (_) {}
    }
    setRecording(null);
    setRecordingStartedAt(null);
    setElapsed(0);
    setAudioUri(null);
    setAudioUploadMeta(null);
    setResult(null);
    setAnalyzing(false);
  }

  useEffect(() => {
    let mounted = true;
    let splashTimer;
    const minimumSplash = new Promise((resolve) => {
      splashTimer = setTimeout(resolve, 500);
    });
    Promise.allSettled([bootstrap(), minimumSplash]).then(() => {
      if (mounted) setShowSplash(false);
    });
    return () => {
      mounted = false;
      clearTimeout(splashTimer);
    };
  }, []);
  useEffect(() => {
    if (!recordingStartedAt) return undefined;
    const id = setInterval(() => setElapsed(Math.floor((Date.now() - recordingStartedAt) / 1000)), 250);
    return () => clearInterval(id);
  }, [recordingStartedAt]);

  async function bootstrap() {
    const [savedToken, savedRefreshToken, savedHistory] = await Promise.all([
      AsyncStorage.getItem(ACCESS_TOKEN_KEY),
      AsyncStorage.getItem(REFRESH_TOKEN_KEY),
      AsyncStorage.getItem(HISTORY_KEY),
    ]);
    if (savedHistory) {
      try { setHistory(JSON.parse(savedHistory)); } catch (_) { await AsyncStorage.removeItem(HISTORY_KEY); }
    }
    if (!savedToken && !savedRefreshToken) {
      setScreen('login');
      return;
    }

    try {
      let activeToken = savedToken;
      let activeRefreshToken = savedRefreshToken;
      let me;
      if (!activeToken) {
        const renewed = await renewSession(activeRefreshToken);
        activeToken = renewed.access_token;
        activeRefreshToken = renewed.refresh_token;
        me = await request('/users/me', { token: activeToken });
      } else {
        try {
          me = await request('/users/me', { token: activeToken });
        } catch (error) {
          if (error.status !== 401 || !activeRefreshToken) throw error;
          const renewed = await renewSession(activeRefreshToken);
          activeToken = renewed.access_token;
          activeRefreshToken = renewed.refresh_token;
          me = await request('/users/me', { token: activeToken });
        }
      }

      setToken(activeToken);
      setRefreshToken(activeRefreshToken);
      if (me.baseline_assessment_status) {
        setScreen('select');
        await Promise.all([loadSentences(activeToken), loadAccountData(activeToken)]);
      } else {
        setScreen('assessment');
        setDashboard({ user_name: me.username, user: me });
      }
    } catch (error) {
      setToken(null);
      setRefreshToken(null);
      setScreen('login');
      if (error.status === 401) {
        await AsyncStorage.multiRemove([ACCESS_TOKEN_KEY, REFRESH_TOKEN_KEY]);
        setNotice('자동 로그인 정보가 만료되었습니다. 다시 로그인해 주세요.');
      } else {
        setNotice('이전 로그인 정보를 확인하고 있습니다.');
      }
    }
  }

  async function renewSession(activeRefreshToken) {
    if (!activeRefreshToken) throw Object.assign(new Error('refresh token이 없습니다.'), { status: 401 });
    const tokens = await request('/auth/token/refresh', {
      method: 'POST',
      body: { refresh_token: activeRefreshToken },
    });
    if (!tokens.access_token || !tokens.refresh_token) throw new Error('로그인 정보를 확인하지 못했습니다.');
    await AsyncStorage.multiSet([
      [ACCESS_TOKEN_KEY, tokens.access_token],
      [REFRESH_TOKEN_KEY, tokens.refresh_token],
    ]);
    return tokens;
  }

  async function authenticatedRequest(path, options = {}) {
    const activeToken = options.token || token || await AsyncStorage.getItem(ACCESS_TOKEN_KEY);
    try {
      return await request(path, { ...options, token: activeToken });
    } catch (error) {
      if (error.status !== 401) throw error;

      const activeRefreshToken = refreshToken || await AsyncStorage.getItem(REFRESH_TOKEN_KEY);
      if (!activeRefreshToken) {
        await clearExpiredSession();
        throw error;
      }

      if (!refreshPromise.current) {
        refreshPromise.current = request('/auth/token/refresh', {
          method: 'POST',
          body: { refresh_token: activeRefreshToken },
        }).then(async (tokens) => {
          await AsyncStorage.multiSet([
            [ACCESS_TOKEN_KEY, tokens.access_token],
            [REFRESH_TOKEN_KEY, tokens.refresh_token],
          ]);
          setToken(tokens.access_token);
          setRefreshToken(tokens.refresh_token);
          return tokens.access_token;
        }).finally(() => { refreshPromise.current = null; });
      }

      try {
        const renewedToken = await refreshPromise.current;
        return request(path, { ...options, token: renewedToken });
      } catch (refreshError) {
        await clearExpiredSession();
        throw refreshError;
      }
    }
  }

  async function clearExpiredSession() {
    await AsyncStorage.multiRemove([ACCESS_TOKEN_KEY, REFRESH_TOKEN_KEY]);
    setToken(null);
    setRefreshToken(null);
    setScreen('login');
    setNotice('로그인이 만료되었습니다. 다시 로그인해 주세요.');
  }

  async function loadSentences(activeToken = token) {
    setLoadingSentences(true);
    try {
      const list = [];
      for (let page = 1; ; page += 1) {
        const data = await request(`/sentences?page=${page}&page_size=100`, { token: activeToken });
        list.push(...(data.results || data).map(normalizeSentence));
        if (!data.next) break;
      }
      if (list.length) {
        const detail = normalizeSentence(await request(`/sentences/${list[0].id}`, { token: activeToken }));
        setSentences([detail, ...list.slice(1)]);
        setSelected(null);
      } else {
        setSentences([]);
        setSelected(null);
      }
      setNotice('');
    } catch (_) {
      setNotice('연습 문장을 불러오지 못해 기본 문장을 표시하고 있습니다.');
      setSentences(demoSentences);
      setSelected(null);
    } finally { setLoadingSentences(false); }
  }

  async function loadAccountData(activeToken = token) {
    try {
      const [records, stats, me] = await Promise.all([
        authenticatedRequest('/records?page_size=100', { token: activeToken }),
        authenticatedRequest('/statistics/summary', { token: activeToken }),
        authenticatedRequest('/users/me', { token: activeToken }),
      ]);
      const normalizedRecords = (records.results || records).map(normalizeRecord);
      setHistory(normalizedRecords);
      setDashboard({
        ...stats,
        total_practices: stats.total_practices ?? stats.total_analyses,
        user_name: me.username,
        user: { id: me.id, username: me.username, name: me.username, age: me.age, phone_number: me.phone_number },
        baseline_assessment_status: me.baseline_assessment_status,
        baseline_self_report_score: me.baseline_self_report_score,
        baseline_discomfort_level: me.baseline_discomfort_level,
      });
      await AsyncStorage.setItem(HISTORY_KEY, JSON.stringify(normalizedRecords));
    } catch (error) {
      if (error.status !== 401) setNotice('일부 학습 기록을 불러오지 못했습니다.');
    }
  }

  const visibleSentences = useMemo(() => sentences.filter((item) => (level === '전체' || item.level === level) && (type === '전체' || item.category === type)), [sentences, level, type]);
  const availableTypes = useMemo(() => ['전체', ...new Set(sentences.map((item) => item.category).filter(Boolean))], [sentences]);
  const navigate = async (next) => {
    if (!token) {
      setScreen('login');
      setNotice('로그인 후 이용할 수 있습니다.');
      return;
    }
    if (screen === 'assessment') {
      setNotice('초기 평가를 완료하거나 건너뛰기를 선택해 주세요.');
      return;
    }
    if (next === 'record' && !selected) { setScreen('select'); setNotice('먼저 연습할 문장을 선택해 주세요.'); return; }
    if (next === 'select' && ['record', 'result', 'feedback'].includes(screen)) await resetPracticeState();
    if (['history', 'profile', 'edit-profile'].includes(next)) {
      loadAccountData(token);
    }
    setScreen(next);
  };

  async function selectSentence(item) {
    if (formatIpa(item.target_ipa)) {
      setSelected(item);
      return item;
    }
    try {
      const detail = normalizeSentence(await request(`/sentences/${item.id}`, { token }));
      setSelected(detail);
      setSentences((items) => items.map((current) => current.id === detail.id ? detail : current));
      return detail;
    } catch (error) {
      Alert.alert('문장을 불러오지 못했습니다', error.message);
      return null;
    }
  }

  async function startPracticeWithSentence(item) {
    await resetPracticeState();
    const detail = await selectSentence(item);
    if (!detail) return;
    setScreen('record');
  }

  async function createCustomSentence({ text, difficulty }) {
    const sentence = normalizeSentence(await authenticatedRequest('/sentences/custom', {
      method: 'POST',
      body: { text, difficulty },
    }));
    setSentences((items) => {
      const filtered = items.filter((item) => item.id !== sentence.id && item.text !== sentence.text);
      return [sentence, ...filtered];
    });
    setSelected(sentence);
    setLevel('전체');
    setType('사용자 지정');
    showToast('사용자 지정 문장이 추가되었습니다.');
    return sentence;
  }

  async function deleteCustomSentence(sentence) {
    if (!sentence?.id || !sentence.isCustom) return;
    await authenticatedRequest(`/sentences/custom/${sentence.id}`, { method: 'DELETE' });
    setSentences((items) => items.filter((item) => item.id !== sentence.id));
    setSelected((current) => (current?.id === sentence.id ? null : current));
    setResult((current) => (current?.sentence?.id === sentence.id ? null : current));
    showToast('사용자 지정 문장을 삭제했습니다.');
  }

  async function startPracticeFromRecord(item) {
    const sentenceText = item.sentence?.text || item.sentence_text;
    const matched = sentences.find((sentence) => sentence.id === item.sentence?.id || sentence.text === sentenceText);
    if (!matched) {
      setNotice('해당 기록의 문장을 찾지 못했습니다. 홈에서 문장을 다시 선택해 주세요.');
      navigate('select');
      return;
    }
    await startPracticeWithSentence(matched);
  }

  async function startRecording() {
    try {
      if (Platform.OS === 'web' && typeof window !== 'undefined' && !window.isSecureContext) {
        Alert.alert('Safari 녹음 제한', '현재 주소가 HTTPS가 아니라서 Safari에서 마이크 녹음이 막힐 수 있습니다. 아래의 음성 파일 선택을 사용하거나 HTTPS 주소로 접속해 주세요.');
        return;
      }
      const isWebRecording = Platform.OS === 'web';
      if (!isWebRecording) await Audio.setAudioModeAsync({ allowsRecordingIOS: false, playsInSilentModeIOS: true });
      await playRecordingCue('start');
      const hasPermission = await ensureMicrophonePermission('발음을 녹음하려면 마이크 권한을 허용해 주세요.');
      if (!hasPermission) return;
      let activeRecording;
      if (isWebRecording) {
        activeRecording = await createWebMicrophoneRecording();
      } else {
        await Audio.setAudioModeAsync({ allowsRecordingIOS: true, playsInSilentModeIOS: true });
        const created = await Audio.Recording.createAsync(Audio.RecordingOptionsPresets.HIGH_QUALITY);
        activeRecording = created.recording;
      }
      await rememberMicrophonePermission();
      setAudioUri(null); setAudioUploadMeta(null); setElapsed(0); setRecording(activeRecording); setRecordingStartedAt(Date.now());
    } catch (error) { Alert.alert('녹음을 시작하지 못했습니다', error.message); }
  }

  function selectPracticeAudioFile(file) {
    if (!file) return;
    setAudioUri(URL.createObjectURL(file));
    setAudioUploadMeta({ name: file.name || `pronunciation-${Date.now()}.m4a`, type: file.type || 'audio/mp4' });
    setElapsed(0);
    setResult(null);
  }

  async function stopRecording() {
    if (!recording) return;
    try {
      await recording.stopAndUnloadAsync();
      const uri = recording.getURI();
      if (!uri || (recording.getBlobSize && recording.getBlobSize() < 1024)) {
        throw new Error('녹음된 음성이 너무 짧거나 비어 있습니다. 1초 이상 말한 뒤 다시 시도해 주세요.');
      }
      setAudioUri(uri);
      if (recording.getMimeType) {
        const type = recording.getMimeType();
        setAudioUploadMeta({ name: `pronunciation-${Date.now()}.${extensionForAudioType(type, 'webm')}`, type });
      }
    } catch (error) { Alert.alert('녹음을 저장하지 못했습니다', error.message); }
    finally {
      setRecording(null);
      setRecordingStartedAt(null);
      if (Platform.OS !== 'web') await Audio.setAudioModeAsync({ allowsRecordingIOS: false });
      await playRecordingCue('stop');
    }
  }

  async function analyze() {
    if (!selected?.id) {
      showToast('먼저 연습 문장을 선택해 주세요.');
      return;
    }
    if (!audioUri) {
      showToast('녹음 후 분석할 수 있습니다.');
      return;
    }
    if (!token) { setScreen('login'); setNotice('분석 결과를 저장하려면 로그인해 주세요.'); return; }
    setAnalyzing(true);
    showToast('발음 분석 요청 중…');
    try {
      const form = new FormData();
      form.append('sentence_id', String(selected.id));
      form.append('consent_to_store', String(consentToStore));
      const isWebRecording = Platform.OS === 'web';
      if (isWebRecording) {
        const audioBlob = await fetch(audioUri).then((response) => response.blob());
        if (audioBlob.size < 1024) throw new Error('녹음된 음성이 너무 짧거나 비어 있습니다. 1초 이상 말한 뒤 다시 녹음해 주세요.');
        const { file, fileName, mimeType } = webAudioFileFromBlob(audioBlob, audioUploadMeta, 'pronunciation');
        console.info('[Jipangi] analysis upload', { fileName, mimeType, size: audioBlob.size, sentenceId: selected.id, apiBaseUrl: API_BASE_URL });
        form.append('audio', file, fileName);
      } else {
        const fileName = audioUploadMeta?.name || `pronunciation-${Date.now()}.m4a`;
        console.info('[Jipangi] analysis upload', { fileName, mimeType: 'audio/mp4', sentenceId: selected.id, apiBaseUrl: API_BASE_URL });
        form.append('audio', { uri: audioUri, name: fileName, type: 'audio/mp4' });
      }
      const accepted = await authenticatedRequest('/analyses', { method: 'POST', token, form });
      showToast('AI가 발음을 분석 중입니다…');
      const data = await waitForAnalysis(accepted.analysis_id);
      const normalized = normalizeResult(data, selected);
      setResult(normalized);
      if (consentToStore) setHistory((old) => [normalized, ...old]);
      showToast('발음 분석이 완료되었습니다.');
      setScreen('result');
      loadAccountData(token);
    } catch (error) {
      console.error('[Jipangi] analysis failed', error);
      showToast('분석에 실패했습니다.');
      Alert.alert('분석에 실패했습니다', error.message || '연결 상태를 확인한 뒤 다시 시도해 주세요.');
    }
    finally { setAnalyzing(false); }
  }

  async function transcribeLifestyleAudio(audioUri, uploadMeta = null) {
    if (!audioUri) throw new Error('녹음 파일이 없습니다.');
    const form = new FormData();
    const isWebRecording = Platform.OS === 'web';
    if (isWebRecording) {
      const audioBlob = await fetch(audioUri).then((response) => response.blob());
      if (!audioBlob.size) throw new Error('녹음 파일이 비어 있습니다. 다시 녹음해 주세요.');
      const { file, fileName } = webAudioFileFromBlob(audioBlob, uploadMeta, 'lifestyle');
      form.append('audio', file, fileName);
    } else {
      const fileName = uploadMeta?.name || `lifestyle-${Date.now()}.m4a`;
      form.append('audio', { uri: audioUri, name: fileName, type: 'audio/mp4' });
    }
    return authenticatedRequest('/lifestyle/transcribe', { method: 'POST', token, form });
  }

  async function waitForAnalysis(analysisId) {
    for (let attempt = 0; attempt < 60; attempt += 1) {
      const analysis = await authenticatedRequest(`/analyses/${analysisId}/status`);
      if (analysis.status === 'completed') {
        return authenticatedRequest(`/analyses/${analysisId}`);
      }
      if (analysis.status === 'failed') {
        throw new Error(analysis.failure_reason || '발음 분석에 실패했습니다. 다시 녹음해 주세요.');
      }
      await new Promise((resolve) => setTimeout(resolve, 2000));
    }
    throw new Error('분석이 지연되고 있습니다. 잠시 후 기록 화면에서 확인해 주세요.');
  }

  async function login(username, password) {
    const data = await request('/auth/login', { method: 'POST', body: { username, password } });
    if (!data.access_token || !data.refresh_token) throw new Error('로그인 정보를 확인하지 못했습니다.');
    await AsyncStorage.multiSet([
      [ACCESS_TOKEN_KEY, data.access_token],
      [REFRESH_TOKEN_KEY, data.refresh_token],
    ]);
    const me = await request('/users/me', { token: data.access_token });
    setToken(data.access_token);
    setRefreshToken(data.refresh_token);
    setNotice('로그인되었습니다.');
    if (me.baseline_assessment_status) {
      setScreen('select');
      loadAccountData(data.access_token);
      loadSentences(data.access_token);
    } else {
      setScreen('assessment');
      setDashboard({ user_name: me.username, user: me });
    }
  }

  async function signup({ username, password, age, phoneNumber }) {
    const data = await request('/auth/signup', {
      method: 'POST',
      body: {
        username,
        password,
        age: age ? Number(age) : null,
        phone_number: normalizePhoneNumberInput(phoneNumber),
      },
    });
    if (!data.access_token || !data.refresh_token) throw new Error('로그인 정보를 확인하지 못했습니다.');
    await AsyncStorage.multiSet([
      [ACCESS_TOKEN_KEY, data.access_token],
      [REFRESH_TOKEN_KEY, data.refresh_token],
    ]);
    setToken(data.access_token);
    setRefreshToken(data.refresh_token);
    setDashboard({ user_name: data.user.username, user: data.user });
    setNotice('회원가입이 완료되었습니다. 초기 상태를 알려 주세요.');
    setScreen('assessment');
  }

  async function updateProfile({ username, age, phoneNumber }) {
    const me = await authenticatedRequest('/users/me', {
      method: 'PATCH',
      body: {
        username,
        age: age ? Number(age) : null,
        phone_number: normalizePhoneNumberInput(phoneNumber),
      },
    });
    setDashboard((current) => ({
      ...current,
      user_name: me.username,
      user: { id: me.id, username: me.username, name: me.username, age: me.age, phone_number: me.phone_number },
      baseline_assessment_status: me.baseline_assessment_status,
      baseline_self_report_score: me.baseline_self_report_score,
      baseline_discomfort_level: me.baseline_discomfort_level,
    }));
    setNotice('회원 정보가 수정되었습니다.');
    setScreen('profile');
    loadAccountData(token);
  }

  async function saveBaselineAssessment(answers, skipped = false) {
    const assessment = await authenticatedRequest('/users/me/baseline-assessment', {
      method: 'POST',
      body: { skipped, answers: skipped ? {} : answers },
    });
    setDashboard((current) => ({
      ...current,
      baseline_assessment_status: assessment.status,
      baseline_self_report_score: assessment.self_report_score,
      baseline_discomfort_level: assessment.discomfort_level,
    }));
    setScreen('select');
    setNotice(skipped ? '초기 평가를 건너뛰었습니다.' : '초기 평가가 저장되었습니다.');
    loadSentences(token);
    loadAccountData(token);
  }

  async function logout() {
    try {
      if (refreshToken) {
        try {
          await request('/auth/logout', {
            method: 'POST',
            token,
            body: { refresh_token: refreshToken },
          });
        } catch (error) {
          if (error.status !== 401) throw error;
          const renewed = await request('/auth/token/refresh', {
            method: 'POST',
            body: { refresh_token: refreshToken },
          });
          await request('/auth/logout', {
            method: 'POST',
            token: renewed.access_token,
            body: { refresh_token: renewed.refresh_token },
          });
        }
      }
    } finally {
      await AsyncStorage.multiRemove([ACCESS_TOKEN_KEY, REFRESH_TOKEN_KEY, HISTORY_KEY]);
      setToken(null);
      setRefreshToken(null);
      setDashboard(null);
      setHistory([]);
      setScreen('login');
      setNotice('로그아웃되었습니다.');
    }
  }

  if (showSplash) {
    return <SafeAreaView style={styles.splash}>
      <StatusBar barStyle="dark-content" /><ExpoStatusBar style="dark" />
      <Text style={styles.splashLogo}>〰 발음도우미</Text>
    </SafeAreaView>;
  }

  return <SafeAreaView style={styles.safe}>
    <StatusBar barStyle="dark-content" /><ExpoStatusBar style="dark" />
    <View style={styles.frame}>
      <View style={styles.header}><Text style={styles.logo}>〰 발음도우미</Text><Text style={styles.headerText}>{token ? '학습 중' : '로그인 필요'}</Text></View>
      {!!notice && <TouchableOpacity style={styles.notice} onPress={() => setNotice('')}><Text style={styles.noticeText}>{notice}</Text></TouchableOpacity>}
      {!token && screen === 'signup' && <SignupScreen onSignup={signup} onBack={() => setScreen('login')} />}
      {!token && screen !== 'signup' && <LoginScreen onLogin={login} onSignup={() => setScreen('signup')} />}
      {!!token && screen === 'assessment' && <BaselineAssessmentScreen onSave={saveBaselineAssessment} />}
      {!!token && screen === 'select' && <SelectScreen list={visibleSentences} selected={selected} history={history} level={level} type={type} types={availableTypes} loading={loadingSentences} onLevel={setLevel} onType={setType} onPreview={selectSentence} onSelect={startPracticeWithSentence} onCreateCustom={createCustomSentence} onDeleteCustom={deleteCustomSentence} />}
      {!!token && screen === 'lifestyle' && <LifestyleScreen onTranscribe={transcribeLifestyleAudio} />}
      {!!token && screen === 'record' && <RecordScreen sentence={selected} recording={!!recording} elapsed={elapsed} ready={!!audioUri} analyzing={analyzing} consentToStore={consentToStore} onConsentChange={setConsentToStore} onRecord={recording ? stopRecording : startRecording} onAudioFile={selectPracticeAudioFile} onAnalyze={analyze} onBack={async () => { await resetPracticeState(); navigate('select'); }} />}
      {!!token && screen === 'result' && <ResultScreen result={result} onFeedback={() => setScreen('feedback')} onRetry={async () => { await resetPracticeState(); navigate('record'); }} />}
      {!!token && screen === 'feedback' && <FeedbackScreen result={result} onBack={() => setScreen('result')} onRetry={async () => { await resetPracticeState(); navigate('record'); }} />}
      {!!token && screen === 'history' && <HistoryScreen history={history} dashboard={dashboard} onPracticeSentence={startPracticeFromRecord} />}
      {!!token && screen === 'profile' && <ProfileScreen dashboard={dashboard} onEdit={() => setScreen('edit-profile')} onLogout={logout} />}
      {!!token && screen === 'edit-profile' && <ProfileEditScreen dashboard={dashboard} onSave={updateProfile} onBack={() => setScreen('profile')} />}
      <BottomNav screen={screen} onNavigate={navigate} />
      <TopToast message={toast} />
    </View>
  </SafeAreaView>;
}

function SelectScreen({ list, selected, history, level, type, types, loading, onLevel, onType, onPreview, onSelect, onCreateCustom, onDeleteCustom }) {
  const [practiceTarget, setPracticeTarget] = useState(null);
  const [customOpen, setCustomOpen] = useState(false);
  const [deletingId, setDeletingId] = useState(null);
  const recentScoresBySentence = useMemo(() => {
    const byId = new Map();
    const byText = new Map();
    (Array.isArray(history) ? history : []).forEach((record) => {
      const score = Number(record?.score ?? record?.pronunciation_score);
      if (!Number.isFinite(score)) return;
      const sentenceId = record?.sentence?.id ?? record?.sentence_id;
      const sentenceText = record?.sentence?.text || record?.sentence_text || record?.sentence;
      if (sentenceId && !byId.has(sentenceId)) byId.set(sentenceId, score);
      if (sentenceText && !byText.has(sentenceText)) byText.set(sentenceText, score);
    });
    return { byId, byText };
  }, [history]);
  const recentScoreLabel = (item) => {
    const score = recentScoresBySentence.byId.get(item.id) ?? recentScoresBySentence.byText.get(item.text);
    return Number.isFinite(score) ? `최근 ${Math.round(score)}점` : '첫 연습이에요!';
  };
  const pressSentence = async (item) => {
    if (selected?.id === item.id) {
      setPracticeTarget(item);
      return;
    }
    await onPreview(item);
  };
  const confirmPractice = async () => {
    if (!practiceTarget) return;
    const target = practiceTarget;
    setPracticeTarget(null);
    await onSelect(target);
  };
  const performDeleteCustom = async (item) => {
    setDeletingId(item.id);
    try {
      await onDeleteCustom(item);
      if (practiceTarget?.id === item.id) setPracticeTarget(null);
    } catch (error) {
      Alert.alert('삭제하지 못했습니다', error.message || '잠시 후 다시 시도해 주세요.');
    } finally {
      setDeletingId(null);
    }
  };
  const requestDeleteCustom = (item) => {
    if (Platform.OS === 'web' && typeof window !== 'undefined') {
      if (window.confirm('이 사용자 지정 문장을 홈에서 삭제할까요? 기존 연습 기록은 유지됩니다.')) {
        performDeleteCustom(item);
      }
      return;
    }
    Alert.alert('사용자 지정 문장 삭제', '이 문장을 홈에서 삭제할까요? 기존 연습 기록은 유지됩니다.', [
      { text: '취소', style: 'cancel' },
      { text: '삭제', style: 'destructive', onPress: () => performDeleteCustom(item) },
    ]);
  };
  return <ScrollView contentContainerStyle={styles.content}><Text style={styles.eyebrow}>오늘의 연습</Text><Text style={styles.title}>내 수준에 맞는 문장을{`\n`}골라 보세요</Text><Text style={styles.subtitle}>난이도와 발음 유형을 선택해 문장을 찾을 수 있습니다.</Text>
    <Button text="사용자 지정 문장 추가" onPress={() => setCustomOpen(true)} />
    <Text style={styles.label}>난이도</Text><Chips values={LEVELS} selected={level} onChange={onLevel} />
    <Text style={styles.label}>카테고리</Text><Chips values={types} selected={type} onChange={onType} />
    <View style={styles.rowBetween}><Text style={styles.sectionTitle}>연습 문장</Text>{loading && <ActivityIndicator color={COLORS.primary} />}</View>
    {list.map((item) => {
      const isSelected = selected?.id === item.id;
      return <TouchableOpacity key={item.id} onPress={() => pressSentence(item)} style={[styles.card, isSelected && styles.cardActive]}><View style={styles.rowBetween}><View style={styles.sentenceLeftMeta}><Badge text={item.category} />{isSelected && <Text style={styles.sentenceScoreText}>{recentScoreLabel(item)}</Text>}</View><View style={styles.sentenceRightMeta}>{item.isCustom && <Pressable hitSlop={8} disabled={deletingId === item.id} style={[styles.deletePill, deletingId === item.id && styles.disabled]} onPress={(event) => { event?.stopPropagation?.(); requestDeleteCustom(item); }}><Text style={styles.deletePillText}>{deletingId === item.id ? '삭제 중' : '삭제'}</Text></Pressable>}<Text style={styles.muted}>{item.level}</Text></View></View><Text style={styles.sentence}>{item.text}</Text>{item.recommendation_reason ? <Text style={styles.reason}>{item.recommendation_reason}</Text> : null}</TouchableOpacity>;
    })}
    {!list.length && <Text style={styles.empty}>조건에 맞는 문장이 없습니다.</Text>}
    <Button text="이 문장으로 연습 시작" onPress={() => setPracticeTarget(selected)} disabled={!selected} />
    <ConfirmPracticeModal sentence={practiceTarget} onCancel={() => setPracticeTarget(null)} onConfirm={confirmPractice} />
    <CustomSentenceModal visible={customOpen} onCancel={() => setCustomOpen(false)} onCreate={async (payload) => {
      await onCreateCustom(payload);
      setCustomOpen(false);
    }} />
  </ScrollView>;
}

function ConfirmPracticeModal({ sentence, onCancel, onConfirm }) {
  return <Modal visible={!!sentence} transparent animationType="fade" onRequestClose={onCancel}><View style={styles.modalBackdrop}><View style={styles.modalCard}><Text style={styles.modalEyebrow}>연습 시작</Text><Text style={styles.modalTitle}>연습하시겠습니까?</Text><Text style={styles.modalSentence}>{sentence?.text}</Text><View style={styles.modalActions}><TouchableOpacity style={styles.modalCancel} onPress={onCancel}><Text style={styles.modalCancelText}>취소</Text></TouchableOpacity><TouchableOpacity style={styles.modalConfirm} onPress={onConfirm}><Text style={styles.modalConfirmText}>연습</Text></TouchableOpacity></View></View></View></Modal>;
}

function CustomSentenceModal({ visible, onCancel, onCreate }) {
  const [text, setText] = useState('');
  const [difficulty, setDifficulty] = useState('easy');
  const [saving, setSaving] = useState(false);
  const { message: toast, show: showToast } = useTransientToast();
  const levels = [
    { value: 'easy', label: '초급' },
    { value: 'normal', label: '중급' },
    { value: 'hard', label: '상급' },
    { value: 'special', label: '심화' },
  ];
  const submit = async () => {
    const cleaned = text.trim().replace(/\s+/g, ' ');
    if (!cleaned) return showToast('문장을 입력해 주세요.');
    if (cleaned.length > 255) return showToast('문장은 255자 이내로 입력해 주세요.');
    setSaving(true);
    try {
      await onCreate({ text: cleaned, difficulty });
      setText('');
      setDifficulty('easy');
    } catch (error) {
      showToast(error.message || '문장을 추가하지 못했습니다.');
    } finally {
      setSaving(false);
    }
  };
  return <Modal visible={visible} transparent animationType="fade" onRequestClose={onCancel}><View style={styles.modalBackdrop}><View style={styles.modalCard}><Text style={styles.modalEyebrow}>사용자 지정</Text><Text style={styles.modalTitle}>연습할 문장을 직접 추가해요</Text><Text style={styles.subtitle}>자주 쓰는 문장을 저장하면 홈의 사용자 지정 카테고리에서 바로 연습할 수 있습니다.</Text><TextInput value={text} onChangeText={setText} style={[styles.input, styles.customSentenceInput]} placeholder="예: 오늘은 천천히 또박또박 말해요." multiline /><Text style={styles.label}>난이도</Text><View style={styles.customLevelRow}>{levels.map((item) => <Pressable key={item.value} hitSlop={6} style={[styles.customLevel, difficulty === item.value && styles.customLevelActive]} onPress={() => setDifficulty(item.value)}><Text style={[styles.chipText, difficulty === item.value && styles.chipTextActive]}>{item.label}</Text></Pressable>)}</View><View style={styles.modalActions}><Pressable hitSlop={8} style={styles.modalCancel} onPress={onCancel} disabled={saving}><Text style={styles.modalCancelText}>취소</Text></Pressable><Pressable hitSlop={8} style={[styles.modalConfirm, saving && styles.disabled]} onPress={submit} disabled={saving}><Text style={styles.modalConfirmText}>{saving ? '추가 중…' : '추가'}</Text></Pressable></View><TopToast message={toast} /></View></View></Modal>;
}

function RecordScreen({ sentence, recording, elapsed, ready, analyzing, consentToStore, onConsentChange, onRecord, onAudioFile, onAnalyze, onBack }) {
  const [showHint, setShowHint] = useState(false);
  const blockedWebRecording = Platform.OS === 'web' && typeof window !== 'undefined' && !window.isSecureContext;
  return <ScrollView contentContainerStyle={styles.content}><TouchableOpacity onPress={onBack}><Text style={styles.back}>‹ 문장 다시 고르기</Text></TouchableOpacity><Text style={styles.eyebrow}>음성 녹음</Text><Text style={styles.title}>문장을 천천히{`\n`}말해 보세요</Text>
    <View style={styles.practice}><Text style={styles.label}>연습 문장</Text><Text style={styles.sentence}>{sentence.text}</Text><TouchableOpacity style={styles.hintToggle} onPress={() => setShowHint((value) => !value)}><Text style={styles.hintToggleText}>{showHint ? 'IPA 힌트 숨기기' : 'IPA 힌트 보기'}</Text><Text style={styles.hintToggleIcon}>{showHint ? '⌃' : '⌄'}</Text></TouchableOpacity>{showHint && <Text style={styles.ipaHint}>{formatIpa(sentence.target_ipa) || '이 문장의 IPA 힌트가 없습니다.'}</Text>}</View>
    <View style={[styles.recordBox, recording && styles.recording]}><Text style={styles.recordState}>{blockedWebRecording ? '보안 연결 필요' : recording ? '● 녹음 중' : ready ? '✓ 녹음 완료' : '마이크 버튼을 눌러 시작'}</Text><Text style={styles.timer}>{String(Math.floor(elapsed / 60)).padStart(2, '0')}:{String(elapsed % 60).padStart(2, '0')}</Text><TouchableOpacity disabled={blockedWebRecording} accessibilityLabel={recording ? '녹음 정지' : '녹음 시작'} style={[styles.mic, recording && styles.micLive, blockedWebRecording && styles.disabled]} onPress={onRecord}><Text style={styles.micText}>{blockedWebRecording ? '🔒' : recording ? '■' : '●'}</Text></TouchableOpacity><Text style={styles.muted}>{blockedWebRecording ? '현재 주소에서는 마이크를 사용할 수 없습니다. 파일 선택으로 음성을 올려 주세요.' : recording ? '완료되면 버튼을 다시 누르세요.' : ready ? '아래 버튼을 눌러 발음 분석을 시작하세요.' : '녹음이 완료되면 분석 버튼이 나타납니다.'}</Text></View>
    <WebAudioFilePicker label="음성 파일 선택해서 분석" onFile={onAudioFile} />
    <View style={styles.consentRow}><View style={styles.consentText}><Text style={styles.label}>학습 기록 저장</Text><Text style={styles.muted}>동의하면 분석 결과를 기록과 통계에 보관합니다.</Text></View><Switch value={consentToStore} onValueChange={onConsentChange} /></View>
    {ready && <Button text={analyzing ? '발음 분석 중…' : '발음 분석하기'} onPress={onAnalyze} disabled={analyzing} />}
    <AnalysisLoadingModal visible={analyzing} />
  </ScrollView>;
}

function AnalysisLoadingModal({ visible }) {
  return <Modal visible={visible} transparent animationType="fade">
    <View style={styles.modalBackdrop}>
      <View style={[styles.modalCard, styles.analysisModal]}>
        <ActivityIndicator color={COLORS.primary} size="large" />
        <Text style={styles.analysisModalTitle}>한국어 특화 IPA 분석 중</Text>
        <Text style={styles.analysisModalText}>학습시킨 Allosaurus 체크포인트가 사용자의 음성을 IPA 기호로 변환하고 있습니다.</Text>
        <View style={styles.analysisAppealBox}>
          <Text style={styles.analysisAppealItem}>• 한국어 발음 특성을 반영해 IPA 기호 체계를 재정의했습니다.</Text>
          <Text style={styles.analysisAppealItem}>• 경음·격음·받침·연음처럼 한국어에서 중요한 차이를 비교합니다.</Text>
          <Text style={styles.analysisAppealItem}>• 변환된 사용자 IPA와 정답 IPA를 정렬해 점수와 교정 피드백을 생성합니다.</Text>
        </View>
      </View>
    </View>
  </Modal>;
}

function normalizeResult(data, sentence) {
  const feedback = data.feedback || data.correction_feedback || {};
  return { id: data.analysis_id || data.id || Date.now(), sentence: normalizeSentence(data.sentence || sentence), score: data.score ?? data.pronunciation_score ?? 0, target_ipa: data.target_ipa || sentence.target_ipa, user_ipa: data.recognized_ipa || data.user_ipa || data.predicted_ipa || [], errors: data.errors || data.pronunciation_errors || [], feedback: { summary: feedback.summary || data.feedback_summary || '분석 결과를 확인해 보세요.', detail: feedback.detail || feedback.content || data.feedback_detail || '', priority: feedback.priority || (feedback.priority_items || []).join(', ') || data.priority_correction || '' }, created_at: data.created_at || new Date().toISOString() };
}

function ResultScreen({ result, onFeedback, onRetry }) {
  if (!result) return <View style={styles.center}><Text>분석 결과가 없습니다.</Text></View>;
  return <ScrollView contentContainerStyle={styles.content}><Text style={styles.eyebrow}>분석 결과</Text><Text style={styles.title}>내 발음이 이렇게{`\n`}인식됐어요</Text><View style={styles.scoreCard}><Text style={styles.score}>{Math.round(result.score)}<Text style={styles.scoreUnit}>점</Text></Text><Text style={styles.scoreCaption}>{result.score >= 80 ? '좋아요! 이 흐름을 유지해 보세요.' : '오류 음소를 중심으로 다시 연습해 보세요.'}</Text></View>
    <View style={styles.card}><Text style={styles.label}>연습 문장</Text><Text style={styles.sentence}>{result.sentence.text}</Text></View><Text style={styles.sectionTitle}>분석된 IPA</Text><IpaLine label="내 발음 IPA" value={result.user_ipa} errors={result.errors} emphasized /><IpaLine label="정답 IPA" value={result.target_ipa} />
    <Text style={styles.sectionTitle}>다르게 발음된 음소</Text>{result.errors.length ? result.errors.map((error, index) => <ErrorSummary key={error.sequence ?? error.id ?? index} error={error} />) : <Text style={styles.empty}>감지된 음소 오류가 없습니다.</Text>}
    <Button text="교정 피드백 받기" onPress={onFeedback} /><Button text="다시 녹음하기" onPress={onRetry} />
  </ScrollView>;
}

function FeedbackScreen({ result, onBack, onRetry }) {
  const [articulationError, setArticulationError] = useState(null);
  if (!result) return <View style={styles.center}><Text>교정 피드백이 없습니다.</Text></View>;
  const feedbackUnits = groupFeedbackErrors(result.errors || [], result.sentence);
  const visibleFeedbackUnits = feedbackUnits.slice(0, 4);
  const hiddenErrorCount = Math.max(0, feedbackUnits.length - visibleFeedbackUnits.length);
  return <ScrollView contentContainerStyle={styles.content}><TouchableOpacity onPress={onBack}><Text style={styles.back}>‹ 분석 결과로 돌아가기</Text></TouchableOpacity><Text style={styles.eyebrow}>교정 피드백</Text><Text style={styles.title}>다음 연습은 여기부터{`\n`}시작해 볼게요</Text>
    <View style={styles.feedback}><Text style={styles.feedbackTitle}>{result.feedback.summary}</Text>{!!result.feedback.detail && <Text style={styles.feedbackText}>{result.feedback.detail}</Text>}{!!result.feedback.priority && <Text style={styles.priority}>우선 연습: {result.feedback.priority}</Text>}</View>
    <Text style={styles.sectionTitle}>오류별 피드백</Text>{visibleFeedbackUnits.length ? visibleFeedbackUnits.map((unit, index) => { const error = unit.primaryError; return <Pressable key={unit.key || index} style={({ pressed }) => [styles.errorRow, pressed && styles.buttonPressed]} onPress={() => setArticulationError(error)}><View style={styles.rowBetween}><ErrorUnitSummary unit={unit} /><Text style={styles.visualHint}>혀모양 보기</Text></View><ErrorWordHighlight error={error} sentence={result.sentence} highlightIndexes={unit.highlightIndexes} />{!!error.specific_feedback?.summary && <Text style={styles.errorFeedbackTitle}>{error.specific_feedback.summary}</Text>}{!!error.specific_feedback?.content && <Text style={styles.errorFeedback}>{error.specific_feedback.content}</Text>}{!!error.specific_feedback?.practice_tip && <Text style={styles.errorFeedback}>연습 팁: {error.specific_feedback.practice_tip}</Text>}</Pressable>; }) : <Text style={styles.empty}>별도로 교정할 음소가 없습니다.</Text>}
    {hiddenErrorCount > 0 && <Text style={styles.limitedNotice}>핵심 발음 단위 4개만 먼저 보여드려요. 나머지 {hiddenErrorCount}개는 분석 IPA를 보며 천천히 다시 확인할 수 있습니다.</Text>}
    <Button text="다시 연습하기" onPress={onRetry} />
    <ArticulationModal result={result} error={articulationError} onClose={() => setArticulationError(null)} />
  </ScrollView>;
}

function ArticulationModal({ result, error, onClose }) {
  const targetPhone = errorTargetPhone(error) || '∅';
  const recognizedPhone = errorRecognizedPhone(error) || '∅';
  const position = errorPosition(error);
  const targetTokens = ipaTokens(result?.target_ipa);
  const targetFlow = ipaWindow(targetTokens, position, targetPhone);
  const targetProfile = phoneProfile(targetPhone);
  const recognizedProfile = phoneProfile(recognizedPhone);
  return <Modal visible={!!error} transparent animationType="fade" onRequestClose={onClose}>
    <View style={styles.modalBackdrop}>
      <View style={[styles.modalCard, styles.articulationModal]}>
        <View style={styles.rowBetween}>
          <View style={{ flex: 1, paddingRight: 12 }}>
            <Text style={styles.modalEyebrow}>혀모양 시각화</Text>
            <Text style={styles.modalTitle}>어디가 달랐는지 볼게요</Text>
          </View>
          <Pressable hitSlop={8} style={styles.closePill} onPress={onClose}>
            <Text style={styles.closePillText}>닫기</Text>
          </Pressable>
        </View>
        <ScrollView style={styles.articulationScroll} contentContainerStyle={styles.articulationScrollContent} showsVerticalScrollIndicator>
          <ErrorWordHighlight error={error} sentence={result?.sentence} />
          <Text style={styles.articulationLead}>오류 위치의 앞뒤 IPA 흐름을 기준으로 정답 발음과 내 발음의 혀 위치를 비교합니다. 이 그림은 음성학 자료를 단순화한 교육용 다이어그램입니다.</Text>
          <IpaFlow title="정답 IPA 흐름" tokens={targetFlow} focusPhone={targetPhone} color={COLORS.primary} />
          <ArticulationTransitionPanel targetPhone={targetPhone} recognizedPhone={recognizedPhone} targetProfile={targetProfile} recognizedProfile={recognizedProfile} />
          <View style={styles.compareBox}>
            <Text style={styles.compareTitle}>교정 방향</Text>
            <Text style={styles.compareText}>{targetProfile.description}{recognizedPhone !== '∅' ? ` 현재 인식된 ${recognizedPhone} 발음과 비교하며, 정답 발음의 강조 지점에 혀를 더 가깝게 맞춰 보세요.` : ' 누락된 소리는 정답 발음의 혀 위치를 천천히 만든 뒤 짧게라도 소리를 내는 연습부터 시작해 보세요.'}</Text>
          </View>
          <View style={styles.referenceBox}>
            <Text style={styles.referenceTitle}>혀모양 시각화 참고 자료</Text>
            {ARTICULATION_REFERENCES.map((item) => <View key={item.title} style={styles.referenceItem}><Text style={styles.referenceName}>{item.title}</Text><Text style={styles.referenceText}>{item.detail}</Text></View>)}
            <Text style={styles.referenceUrl}>※ 위 자료의 조음 위치·방식 기준을 앱 화면에 맞게 단순화한 교육용 시각화입니다.</Text>
          </View>
        </ScrollView>
      </View>
    </View>
  </Modal>;
}

function IpaFlow({ title, tokens, focusPhone, color }) {
  return <View style={styles.ipaFlow}><Text style={styles.label}>{title}</Text><View style={styles.ipaFlowTokens}>{tokens.map((token, index) => <View key={`${title}-${token}-${index}`} style={[styles.ipaFlowToken, token === focusPhone && { backgroundColor: color }]}><Text style={[styles.ipaFlowText, token === focusPhone && styles.ipaFlowTextActive]}>{token}</Text></View>)}</View></View>;
}

function ArticulationPanel({ title, profile, tone }) {
  return <View style={styles.articulationPanel}><Text style={styles.articulationTitle}>{title}</Text><TongueDiagram profile={profile} tone={tone} /><Text style={styles.articulationLabel}>{profile.label}</Text><Text style={styles.articulationDescription}>{profile.description}</Text></View>;
}

function ArticulationTransitionPanel({ targetPhone, recognizedPhone, targetProfile, recognizedProfile }) {
  return <View style={styles.articulationPanel}>
    <Text style={styles.articulationTitle}>혀 위치 이동 다이어그램</Text>
    <TongueTransitionDiagram targetProfile={targetProfile} recognizedProfile={recognizedProfile} />
    <View style={styles.transitionLegend}>
      <View style={styles.legendItem}><View style={[styles.legendDot, styles.userDot]} /><Text style={styles.muted}>현재 인식: {recognizedPhone}</Text></View>
      <View style={styles.legendItem}><View style={[styles.legendDot, styles.targetDot]} /><Text style={styles.muted}>목표 발음: {targetPhone}</Text></View>
    </View>
    <Text style={styles.articulationLabel}>{recognizedProfile.label} → {targetProfile.label}</Text>
    <Text style={styles.articulationDescription}>분홍색 혀와 검은 점이 0.1초 간격으로 현재 위치에서 목표 위치까지 움직입니다. 화살표 방향을 따라 혀끝·혀몸·혀뒤쪽 중 강조 지점을 조절해 보세요.</Text>
  </View>;
}

function TongueTransitionDiagram({ targetProfile, recognizedProfile }) {
  const [animationStep, setAnimationStep] = useState(0);
  const targetPath = compactTonguePath(TONGUE_PATHS[targetProfile.diagramKey] || TONGUE_PATHS.neutral);
  const recognizedPath = compactTonguePath(TONGUE_PATHS[recognizedProfile.diagramKey] || TONGUE_PATHS.neutral);
  const [tx, ty] = compactTonguePoint(targetProfile.highlight);
  const [ux, uy] = compactTonguePoint(recognizedProfile.highlight);
  useEffect(() => {
    const timer = setInterval(() => setAnimationStep((step) => (step + 1) % 14), 100);
    return () => clearInterval(timer);
  }, []);
  const progress = Math.min(animationStep, 10) / 10;
  const animatedPath = interpolatePath(recognizedPath, targetPath, progress);
  const mx = interpolateValue(ux, tx, progress);
  const my = interpolateValue(uy, ty, progress);
  const tongueFillPath = `${animatedPath} C ${compactTongueX(230).toFixed(1)} 184 ${compactTongueX(130).toFixed(1)} 180 ${compactTongueX(62).toFixed(1)} 154 Z`;
  const arrowAngle = Math.atan2(ty - uy, tx - ux);
  const arrowX1 = tx - Math.cos(arrowAngle - 0.48) * 9;
  const arrowY1 = ty - Math.sin(arrowAngle - 0.48) * 9;
  const arrowX2 = tx - Math.cos(arrowAngle + 0.48) * 9;
  const arrowY2 = ty - Math.sin(arrowAngle + 0.48) * 9;
  return <ImageBackground source={VOCAL_TRACT_BACKGROUND_IMAGE} resizeMode="cover" imageStyle={styles.transitionImage} style={styles.transitionCanvas}>
    <Svg width="100%" height="240" viewBox="0 0 320 240">
      <Defs>
        <LinearGradient id="tongueGrad" x1="0" y1="0" x2="1" y2="1">
          <Stop offset="0" stopColor="#FF9AAE" />
          <Stop offset="0.55" stopColor="#E86C86" />
          <Stop offset="1" stopColor="#B94D63" />
        </LinearGradient>
      </Defs>
      <Path d={tongueFillPath} fill="url(#tongueGrad)" opacity="0.76" stroke="#9F344E" strokeWidth="2.2" strokeLinejoin="round" />
      <Path d={recognizedPath} stroke="#EF4444" strokeWidth="4" fill="none" strokeLinecap="round" strokeLinejoin="round" opacity="0.34" strokeDasharray="5 4" />
      <Path d={targetPath} stroke="#2F80ED" strokeWidth="4" fill="none" strokeLinecap="round" strokeLinejoin="round" opacity="0.94" />
      <Path d={animatedPath} stroke="#C026D3" strokeWidth="7" fill="none" strokeLinecap="round" strokeLinejoin="round" opacity="0.88" />
      <Line x1={ux} y1={uy} x2={tx} y2={ty} stroke="#2F80ED" strokeWidth="3.2" strokeDasharray="5 4" strokeLinecap="round" />
      <Path d={`M ${tx} ${ty} L ${arrowX1} ${arrowY1} M ${tx} ${ty} L ${arrowX2} ${arrowY2}`} stroke="#2F80ED" strokeWidth="3.2" strokeLinecap="round" />
      <Circle cx={ux} cy={uy} r="10" fill="#EF4444" opacity="0.18" />
      <Circle cx={ux} cy={uy} r="5" fill="#EF4444" />
      <Circle cx={tx} cy={ty} r="12" fill="#2F80ED" opacity="0.2" />
      <Circle cx={tx} cy={ty} r="6" fill="#2F80ED" />
      <Circle cx={mx} cy={my} r="4.5" fill="#111827" opacity="0.82" />
    </Svg>
  </ImageBackground>;
}

function TongueDiagram({ profile, tone }) {
  const path = compactTonguePath(TONGUE_PATHS[profile.diagramKey] || TONGUE_PATHS.neutral);
  const [hx, hy] = compactTonguePoint(profile.highlight);
  const mainColor = tone === 'user' ? COLORS.danger : COLORS.primary;
  return <ImageBackground source={VOCAL_TRACT_BACKGROUND_IMAGE} resizeMode="cover" imageStyle={styles.tongueImage} style={styles.tongueCanvas}><Svg width="100%" height="190" viewBox="0 0 320 190">
    <Path d="M48 91 C32 112 34 142 58 158" stroke="#334155" strokeWidth="5" fill="none" strokeLinecap="round" />
    <Path d="M62 82 C112 39 209 34 279 87" stroke="#334155" strokeWidth="5" fill="none" strokeLinecap="round" />
    <Path d="M68 170 C106 180 190 181 282 158" stroke="#CBD5E1" strokeWidth="4" fill="none" strokeLinecap="round" />
    <Line x1="78" y1="89" x2="78" y2="110" stroke="#94A3B8" strokeWidth="3" strokeLinecap="round" />
    <Line x1="93" y1="80" x2="93" y2="104" stroke="#94A3B8" strokeWidth="3" strokeLinecap="round" />
    <SvgText x="72" y="72" fontSize="10" fill="#64748B" fontWeight="700">치경</SvgText>
    <SvgText x="154" y="53" fontSize="10" fill="#64748B" fontWeight="700">경구개</SvgText>
    <SvgText x="220" y="77" fontSize="10" fill="#64748B" fontWeight="700">연구개</SvgText>
    <Path d={path} stroke={mainColor} strokeWidth="9" fill="none" strokeLinecap="round" strokeLinejoin="round" />
    <Circle cx={hx} cy={hy} r="11" fill={mainColor} opacity="0.22" />
    <Circle cx={hx} cy={hy} r="6" fill={mainColor} />
    <SvgText x={Math.min(hx + 12, 232)} y={Math.max(hy - 10, 18)} fontSize="11" fill={mainColor} fontWeight="800">{profile.placeLabel}</SvgText>
  </Svg></ImageBackground>;
}

function LifestyleScreen({ onTranscribe }) {
  const [recording, setRecording] = useState(null);
  const [transcribing, setTranscribing] = useState(false);
  const [heardText, setHeardText] = useState('');
  const [replyText, setReplyText] = useState('');
  const [speaking, setSpeaking] = useState(false);

  useEffect(() => () => {
    if (Platform.OS === 'web' && typeof window !== 'undefined' && window.speechSynthesis) {
      window.speechSynthesis.cancel();
    }
  }, []);

  const startListening = async () => {
    try {
      if (Platform.OS === 'web' && typeof window !== 'undefined' && !window.isSecureContext) {
        Alert.alert('Safari 녹음 제한', '현재 주소가 HTTPS가 아니라서 Safari에서 마이크 녹음이 막힐 수 있습니다. HTTPS 주소로 접속해 주세요.');
        return;
      }
      await Audio.setAudioModeAsync({ allowsRecordingIOS: false, playsInSilentModeIOS: true });
      await playRecordingCue('start');
      const hasPermission = await ensureMicrophonePermission('주변 말을 받아쓰려면 마이크 권한을 허용해 주세요.');
      if (!hasPermission) return;
      await Audio.setAudioModeAsync({ allowsRecordingIOS: true, playsInSilentModeIOS: true });
      const created = await Audio.Recording.createAsync(Audio.RecordingOptionsPresets.HIGH_QUALITY);
      await rememberMicrophonePermission();
      setRecording(created.recording);
    } catch (error) {
      Alert.alert('녹음을 시작하지 못했습니다', error.message);
    }
  };

  const stopListening = async () => {
    if (!recording) return;
    let uri = '';
    try {
      await recording.stopAndUnloadAsync();
      uri = recording.getURI();
    } catch (error) {
      Alert.alert('녹음을 저장하지 못했습니다', error.message);
      return;
    } finally {
      setRecording(null);
      await Audio.setAudioModeAsync({ allowsRecordingIOS: false });
      await playRecordingCue('stop');
    }
    if (!uri) return;
    setTranscribing(true);
    try {
      const result = await onTranscribe(uri);
      setHeardText(result.text || '');
      if (!result.text) Alert.alert('받아쓰기 결과 없음', '음성이 너무 짧거나 조용해서 문장을 인식하지 못했습니다.');
    } catch (error) {
      Alert.alert('받아쓰기에 실패했습니다', error.message || '주변 소음을 줄이고 다시 시도해 주세요.');
    } finally {
      setTranscribing(false);
    }
  };

  const speakReply = () => {
    const text = replyText.trim();
    if (!text) {
      Alert.alert('읽을 문장이 없습니다', '음성으로 들을 문장을 먼저 입력해 주세요.');
      return;
    }
    if (Platform.OS !== 'web' || typeof window === 'undefined' || !window.speechSynthesis || typeof window.SpeechSynthesisUtterance !== 'function') {
      Alert.alert('음성 읽기 미지원', '현재 환경에서는 텍스트 음성 읽기를 사용할 수 없습니다.');
      return;
    }
    window.speechSynthesis.cancel();
    const utterance = new window.SpeechSynthesisUtterance(text);
    utterance.lang = 'ko-KR';
    utterance.rate = 0.88;
    utterance.pitch = 1.02;
    const voices = window.speechSynthesis.getVoices();
    const koreanVoice = voices.find((voice) => voice.lang?.toLowerCase().startsWith('ko'));
    if (koreanVoice) utterance.voice = koreanVoice;
    utterance.onend = () => setSpeaking(false);
    utterance.onerror = () => setSpeaking(false);
    setSpeaking(true);
    window.speechSynthesis.speak(utterance);
  };

  const stopSpeaking = () => {
    if (Platform.OS === 'web' && typeof window !== 'undefined' && window.speechSynthesis) {
      window.speechSynthesis.cancel();
    }
    setSpeaking(false);
  };

  return <ScrollView contentContainerStyle={styles.content}><Text style={styles.eyebrow}>생활용</Text><Text style={styles.title}>대화를 듣고{`\n`}음성으로 준비해요</Text><Text style={styles.subtitle}>상대방의 말을 글로 확인하고, 내가 답하고 싶은 문장은 바로 음성으로 들어볼 수 있습니다.</Text>
    <View style={styles.card}><View style={styles.rowBetween}><View style={{ flex: 1, paddingRight: 12 }}><Text style={styles.label}>주변 말소리 받아쓰기</Text><Text style={styles.sentence}>상대방의 말</Text></View><Text style={styles.recordState}>{recording ? '● 듣는 중' : transcribing ? '변환 중' : '대기'}</Text></View><Text style={styles.muted}>{recording ? '상대방의 말이 끝나면 아래 버튼을 다시 눌러 글로 바꿔 주세요.' : '조용한 곳에서 상대방의 말을 짧게 녹음해 주세요.'}</Text><TextInput value={heardText} onChangeText={setHeardText} style={[styles.input, { height: 92, marginTop: 12, textAlignVertical: 'top', paddingTop: 12 }]} placeholder="예: 어디로 가고 싶으세요?" multiline /><Button text={transcribing ? '한글로 변환 중…' : recording ? '듣기 종료하고 변환' : '듣기 시작'} onPress={recording ? stopListening : startListening} disabled={transcribing} /></View>
    <View style={styles.practice}><Text style={styles.label}>내가 답하고 싶은 말</Text><TextInput value={replyText} onChangeText={setReplyText} style={[styles.input, { minHeight: 96, textAlignVertical: 'top', paddingTop: 12 }]} placeholder="예: 병원에 가고 싶어요." multiline /><Button text={speaking ? '읽기 중지' : '음성으로 듣기'} onPress={speaking ? stopSpeaking : speakReply} disabled={!replyText.trim()} /><Text style={styles.ttsHint}>Safari의 한국어 음성으로 문장을 읽어줍니다.</Text></View>
    <View style={styles.card}><Text style={styles.label}>사용 팁</Text><Text style={styles.muted}>짧은 문장을 먼저 입력해 소리를 들어본 뒤, 같은 속도로 천천히 따라 말해 보세요.{`\n`}상대방에게 답하기 전 말할 문장을 귀로 확인하는 용도에 맞췄습니다.</Text></View>
  </ScrollView>;
}

function ErrorSummary({ error }) { return <View><Text style={styles.errorToken}>{error.target_phone || error.expected_phone || error.target || '∅'} → {error.recognized_phone || error.actual_phone || error.user || '∅'}</Text><Text style={styles.errorDescription}>{error.operation || error.error_type || error.type || '음소 차이'}</Text></View>; }

function ErrorUnitSummary({ unit }) {
  const errorCount = unit.errors?.length || 1;
  return <View><Text style={styles.errorUnitTitle}>‘{unit.unitText}’ 발음 단위</Text><Text style={styles.errorDescription}>{errorCount > 1 ? `${errorCount}개 소리 차이를 하나로 묶었어요` : '이 부분을 먼저 다듬어 보세요'}</Text></View>;
}

function ErrorWordHighlight({ error, sentence, highlightIndexes: overrideHighlightIndexes }) {
  const word = String(error?.word || '').trim();
  if (!word) return null;
  const highlightIndexes = overrideHighlightIndexes || highlightIndexesForErrorWord(error, sentence);
  const span = wordSpanForError(error, sentence);
  const syllables = Array.isArray(span?.syllables) && span.syllables.length
    ? span.syllables
    : Array.from(word).map((character) => ({ text: character, ipa: hangulCharacterToIpa(character) }));
  return <View style={styles.errorWordBox}>
    <Text style={styles.errorWordLabel}>오류 단어</Text>
    <View style={styles.errorWordSyllables}>
      {syllables.map((syllable, index) => {
        const marked = highlightIndexes.has(index);
        const text = syllable.text || Array.from(word)[index] || '';
        const ipa = Array.isArray(syllable.ipa) ? syllable.ipa.join(' ') : '';
        return <View key={`${text}-${index}`} style={[styles.errorSyllableChip, marked && styles.errorSyllableChipMarked]}>
          <Text style={[styles.errorSyllableText, marked && styles.errorSyllableTextMarked]}>{text}</Text>
          {!!ipa && <Text style={[styles.errorSyllableIpa, marked && styles.errorSyllableIpaMarked]}>{ipa}</Text>}
        </View>;
      })}
    </View>
  </View>;
}

function IpaLine({ label, value, errors = [], emphasized = false }) { const errorIndexes = new Set(errors.map((e) => e.phone_position ?? e.user_index ?? e.position).filter(Number.isInteger)); const ipa = formatIpa(value) || '표시할 IPA 정보가 없습니다.'; return <View style={[styles.ipaCard, emphasized && styles.ipaCardActive]}><Text style={styles.label}>{label}</Text><View style={styles.ipaTokens}>{ipa.split(/\s+/).map((token, index) => <Text key={`${token}-${index}`} style={[styles.token, errorIndexes.has(index) && styles.errorToken]}>{token} </Text>)}</View></View>; }

function HistoryScreen({ history, dashboard, onPracticeSentence }) {
  const safeHistory = Array.isArray(history) ? history : [];
  const scoreOf = (item) => Number(item?.score ?? item?.pronunciation_score ?? 0);
  const sentenceKeyOf = (item) => {
    const sentenceId = item?.sentence?.id ?? item?.sentence_id;
    if (sentenceId !== null && sentenceId !== undefined) return `id:${sentenceId}`;
    const sentenceText = item?.sentence?.text || item?.sentence_text || item?.sentence;
    return sentenceText ? `text:${sentenceText}` : `analysis:${item?.id || item?.analysis_id}`;
  };
  const historyScores = safeHistory.map(scoreOf).filter(Number.isFinite);
  const averageScore = Number(dashboard?.average_score);
  const averageValue = Number.isFinite(averageScore) ? Math.round(averageScore) : average(historyScores);
  const totalPractices = dashboard?.total_practices ?? dashboard?.total_analyses ?? safeHistory.length;
  const difficultyStats = Array.isArray(dashboard?.difficulty_stats) ? dashboard.difficulty_stats : [];
  const ruleErrorStats = Array.isArray(dashboard?.rule_error_summary) ? dashboard.rule_error_summary : [];
  const latestRecordsBySentence = new Map();
  [...safeHistory]
    .sort((a, b) => new Date(b?.created_at || 0).getTime() - new Date(a?.created_at || 0).getTime())
    .forEach((item) => {
      const key = sentenceKeyOf(item);
      if (!latestRecordsBySentence.has(key)) latestRecordsBySentence.set(key, item);
    });
  const weakRecords = [...latestRecordsBySentence.values()]
    .filter((item) => {
      const score = scoreOf(item);
      return Number.isFinite(score) && score < 80;
    })
    .sort((a, b) => scoreOf(a) - scoreOf(b))
    .slice(0, 5);
  const renderRecord = (item, index) => {
    const score = scoreOf(item);
    return <TouchableOpacity key={item.id || index} style={styles.history} onPress={() => onPracticeSentence(item)}><View style={styles.historyBody}><Text style={styles.historySentence}>{item.sentence?.text || item.sentence_text || '연습 문장'}</Text><Text style={styles.muted}>{new Date(item.created_at || Date.now()).toLocaleDateString('ko-KR')} · 눌러서 다시 연습</Text></View><Text style={styles.historyScore}>{Number.isFinite(score) ? Math.round(score) : 0}점</Text></TouchableOpacity>;
  };
  return <ScrollView contentContainerStyle={styles.content}><Text style={styles.eyebrow}>나의 기록</Text><Text style={styles.title}>연습이 쌓이고 있어요</Text><View style={styles.stats}><Stat value={dashboard?.streak_days ?? dashboard?.streak ?? 0} label="연속 학습일" /><Stat value={averageValue} label="평균 점수" /><Stat value={totalPractices} label="총 연습" /></View><Text style={styles.sectionTitle}>자주 틀리는 규칙</Text><RuleErrorStats items={ruleErrorStats} /><Text style={styles.sectionTitle}>난이도별 점수 분포</Text><DifficultyHistogram items={difficultyStats} /><Text style={styles.sectionTitle}>다시 연습하면 좋은 문장</Text>{weakRecords.length ? weakRecords.map(renderRecord) : <Text style={styles.empty}>80점 미만 기록이 없습니다.</Text>}<Text style={styles.sectionTitle}>최근 연습</Text>{safeHistory.length ? safeHistory.slice(0, 10).map(renderRecord) : <Text style={styles.empty}>저장된 연습 기록이 없습니다. 분석할 때 “학습 기록 저장”을 켜면 여기에 표시됩니다.</Text>}</ScrollView>;
}

function DifficultyHistogram({ items }) {
  if (!items.length) return <Text style={styles.empty}>난이도별 통계를 만들 기록이 없습니다.</Text>;
  const order = ['easy', 'normal', 'hard', 'special'];
  const labels = { easy: '초급', normal: '중급', hard: '상급', special: '심화' };
  const statsByDifficulty = Object.fromEntries(items.map((item) => [item.difficulty, item]));
  const clamp = (value) => Math.max(0, Math.min(100, Number(value) || 0));
  const maxCount = Math.max(1, ...items.map((item) => Number(item.count) || 0));
  return <View style={styles.histogramCard}><View style={styles.histogramLegend}><View style={styles.legendItem}><View style={[styles.legendDot, styles.countDot]} /><Text style={styles.muted}>횟수</Text></View><View style={styles.legendItem}><View style={[styles.legendDot, styles.scoreDot]} /><Text style={styles.muted}>평균점수</Text></View></View><View style={styles.histogramBody}>{order.map((difficulty) => {
    const item = statsByDifficulty[difficulty] || { difficulty, label: labels[difficulty], count: 0, average_score: 0 };
    const count = Number(item.count) || 0;
    const averageScore = clamp(item.average_score);
    const countHeight = count ? Math.max(14, (count / maxCount) * 116) : 4;
    const scoreHeight = averageScore ? Math.max(14, (averageScore / 100) * 116) : 4;
    return <View key={difficulty} style={styles.histogramGroup}><View style={styles.histogramBars}><View style={[styles.histogramBar, styles.countBar, { height: countHeight }]}><Text style={styles.histogramValue}>{count}</Text></View><View style={[styles.histogramBar, styles.scoreBar, { height: scoreHeight }]}><Text style={styles.histogramValue}>{Math.round(averageScore)}</Text></View></View><Text style={styles.histogramLabel}>{item.label || labels[difficulty]}</Text></View>;
  })}</View></View>;
}

function RuleErrorStats({ items }) {
  const safeItems = (Array.isArray(items) ? items : [])
    .map((item) => ({
      code: item?.category?.code || '',
      name: item?.category?.name || '규칙',
      count: Number(item?.count) || 0,
    }))
    .filter((item) => item.count > 0)
    .slice(0, 5);
  if (!safeItems.length) return <View style={styles.ruleStatsCard}><Text style={styles.empty}>아직 자주 틀리는 규칙 통계가 없습니다.</Text><Text style={styles.ruleStatsHint}>연습 기록이 쌓이면 연음화, 비음화, 경음화 같은 규칙별 오류가 여기에 표시됩니다.</Text></View>;
  const total = safeItems.reduce((sum, item) => sum + item.count, 0);
  const maxCount = Math.max(...safeItems.map((item) => item.count));
  const lead = safeItems[0];
  return <View style={styles.ruleStatsCard}><View style={styles.rowBetween}><View><Text style={styles.ruleStatsTitle}>{lead.name}을 가장 자주 놓쳤어요</Text><Text style={styles.muted}>상위 {safeItems.length}개 규칙 · 총 {total}회</Text></View><View style={styles.ruleStatsBadge}><Text style={styles.ruleStatsBadgeText}>{lead.count}</Text><Text style={styles.ruleStatsBadgeSub}>회</Text></View></View><View style={styles.ruleStatsList}>{safeItems.map((item) => {
    const percent = Math.round((item.count / total) * 100);
    const width = `${Math.max(8, (item.count / maxCount) * 100)}%`;
    return <View key={item.code || item.name} style={styles.ruleStatsRow}><View style={styles.rowBetween}><Text style={styles.ruleStatsName}>{item.name}</Text><Text style={styles.ruleStatsCount}>{item.count}회 · {percent}%</Text></View><View style={styles.ruleStatsTrack}><View style={[styles.ruleStatsBar, { width }]} /></View></View>;
  })}</View><Text style={styles.ruleStatsHint}>많이 나온 규칙부터 같은 카테고리 문장으로 다시 연습해 보세요.</Text></View>;
}

function WebAudioFilePicker({ label, onFile, disabled }) {
  if (Platform.OS !== 'web') return null;
  const inputId = useRef(`audio-file-${Math.random().toString(36).slice(2)}`).current;
  return <View style={styles.webFilePicker}><Text style={styles.muted}>Safari에서 녹음 버튼이 막히면 음성메모 파일을 선택해 주세요.</Text>{React.createElement('label', {
    htmlFor: inputId,
    style: {
      display: 'flex',
      minHeight: 48,
      marginTop: 10,
      borderRadius: 14,
      alignItems: 'center',
      justifyContent: 'center',
      backgroundColor: disabled ? '#A8ACFF' : COLORS.primary,
      color: '#FFFFFF',
      fontSize: 14,
      fontWeight: 900,
    },
  }, label)}{React.createElement('input', {
    id: inputId,
    type: 'file',
    accept: 'audio/*,video/mp4,video/webm',
    capture: 'microphone',
    disabled,
    style: { position: 'absolute', opacity: 0, width: 1, height: 1, pointerEvents: 'none' },
    onChange: (event) => {
      const file = event.target.files?.[0];
      if (file) onFile(file);
      event.target.value = '';
    },
  })}</View>;
}

function peerEncouragement(peerRank) {
  if (!peerRank) return '기록을 몇 번 더 쌓으면 다른 사용자들과의 비교를 볼 수 있어요.';
  const topPercent = Number(peerRank.top_percent);
  if (topPercent <= 10) return '상위권 흐름이 아주 좋습니다. 지금 리듬을 유지하면서 어려운 문장에도 도전해 보세요.';
  if (topPercent <= 30) return '꽤 안정적인 위치에 있어요. 자주 틀리는 음소만 조금 다듬으면 더 올라갈 수 있습니다.';
  if (topPercent <= 60) return '좋은 연습 기록이 쌓이고 있어요. 짧은 문장을 정확히 말하는 루틴부터 이어가면 충분합니다.';
  return '아직 출발선에 가까운 구간이에요. 점수보다 꾸준함을 먼저 잡으면 비교 지표도 금방 따라옵니다.';
}

function PeerRankCard({ peerRank }) {
  if (!peerRank) {
    return <View style={[styles.card, styles.profileCompareCard]}><Text style={styles.label}>사용자 비교</Text><Text style={styles.profileRank}>비교 준비 중</Text><Text style={styles.muted}>{peerEncouragement(null)}</Text></View>;
  }
  return <View style={[styles.card, styles.profileCompareCard]}>
    <View style={styles.profileCompareHeader}>
      <View style={styles.profileCompareMain}>
        <Text style={styles.label}>사용자 비교</Text>
        <Text style={styles.profileRank}>상위 {peerRank.top_percent}%</Text>
        <Text style={styles.muted}>평균 {Math.round(Number(peerRank.average_score) || 0)}점 기준</Text>
      </View>
      <View style={styles.profileRankBadge}>
        <Text style={styles.profileRankBadgeText}>{peerRank.rank}</Text>
        <Text style={styles.profileRankBadgeSub}>/ {peerRank.total_users}</Text>
      </View>
    </View>
    <Text style={styles.profileEncouragement}>{peerEncouragement(peerRank)}</Text>
  </View>;
}

function ProfileMetric({ value, label }) {
  return <View style={styles.profileMetric}><Text style={styles.profileMetricValue}>{value}</Text><Text style={styles.profileMetricLabel}>{label}</Text></View>;
}

function weeklyTrendCopy(trend) {
  if (!trend || !trend.current_count) {
    return {
      title: '이번 주 기록 대기 중',
      body: '이번 주 연습을 시작하면 최근 7일 점수를 기준으로 변화가 보여요. 오늘은 짧은 문장 하나만 또렷하게 가도 충분합니다.',
    };
  }
  const current = Math.round(Number(trend.current_average) || 0);
  const previous = Number(trend.previous_average);
  const delta = Number(trend.delta);
  if (!Number.isFinite(previous)) {
    return {
      title: `이번 주 평균 ${current}점`,
      body: '비교 기준을 만드는 중이에요. 기록이 한 주 더 쌓이면 이전 주보다 얼마나 좋아졌는지 바로 보여드릴게요.',
    };
  }
  if (trend.status === 'big_improvement') {
    return {
      title: `지난주보다 ${Math.round(delta)}점 상승`,
      body: '이전보다 되게 많이 좋아졌어요. 지금처럼 천천히, 정확하게 말하는 연습을 유지하면 좋은 흐름이 계속 이어집니다.',
    };
  }
  if (trend.status === 'improved') {
    return {
      title: `지난주보다 ${Math.round(delta)}점 좋아졌어요`,
      body: '분명히 올라가고 있어요. 자주 틀린 음소를 한 번 더 확인하고 오늘 연습을 가볍게 이어가면 좋겠습니다.',
    };
  }
  if (trend.status === 'maintained') {
    return {
      title: `주간 평균 ${current}점 유지 중`,
      body: '주간 점수를 잘 지키고 있어요. 같은 점수라도 흔들리지 않는 게 실력입니다. 이제 조금 더 긴 문장으로 넓혀봐도 좋아요.',
    };
  }
  return {
    title: `이번 주 평균 ${current}점`,
    body: '요즘은 연습을 조금 더 해주면 좋겠어요. 낮은 점수는 실패가 아니라 다음 연습 문장을 알려주는 신호에 가깝습니다.',
  };
}

function WeeklyTrendCard({ trend }) {
  const copy = weeklyTrendCopy(trend);
  const current = Number(trend?.current_average);
  const previous = Number(trend?.previous_average);
  return <View style={[styles.card, styles.weeklyTrendCard]}>
    <View style={styles.rowBetween}>
      <View style={styles.profileCompareMain}>
        <Text style={styles.label}>주간 점수</Text>
        <Text style={styles.weeklyTrendTitle}>{copy.title}</Text>
      </View>
      <View style={styles.weeklyScoreStack}>
        <Text style={styles.weeklyScoreValue}>{Number.isFinite(current) ? Math.round(current) : '-'}</Text>
        <Text style={styles.weeklyScoreLabel}>이번 주</Text>
      </View>
    </View>
    {Number.isFinite(previous) && <Text style={styles.muted}>지난 7일 {Math.round(current)}점 · 이전 7일 {Math.round(previous)}점</Text>}
    <Text style={styles.profileEncouragement}>{copy.body}</Text>
  </View>;
}

function BaselineCard({ dashboard, levelLabel }) {
  const completed = dashboard?.baseline_assessment_status === 'completed';
  const skipped = dashboard?.baseline_assessment_status === 'skipped';
  return <View style={styles.card}>
    <Text style={styles.label}>초기 평가</Text>
    {completed && <Text style={styles.profileBaselineText}>{levelLabel || '미분류'} · {dashboard.baseline_self_report_score ?? 0}/20</Text>}
    {skipped && <Text style={styles.profileBaselineText}>초기 발음 평가 건너뜀</Text>}
    {!completed && !skipped && <Text style={styles.profileBaselineText}>초기 평가 정보가 없습니다</Text>}
    <Text style={styles.muted}>이 값은 현재 점수와 비교하기 위한 개인 기준값입니다.</Text>
  </View>;
}

function ProfileScreen({ dashboard, onEdit, onLogout }) {
  const user = dashboard?.user || {};
  const levelLabel = { low: '낮음', medium: '보통', high: '높음' }[dashboard?.baseline_discomfort_level];
  const averageScore = Number(dashboard?.average_score);
  const averageValue = Number.isFinite(averageScore) ? Math.round(averageScore) : 0;
  return <ScrollView contentContainerStyle={styles.profileContent}>
    <View style={styles.profileHeader}>
      <View>
        <Text style={styles.eyebrow}>내 정보</Text>
        <Text style={styles.title}>나의 학습 현황</Text>
      </View>
    </View>
    <View style={[styles.card, styles.profileHero]}>
      <View style={styles.profileAvatar}><Text style={styles.profileAvatarText}>{String(dashboard?.user_name || user.name || '학').slice(0, 1).toUpperCase()}</Text></View>
      <View style={styles.profileHeroBody}>
        <Text style={styles.profileName}>{dashboard?.user_name || user.name || '학습자'}</Text>
        <Text style={styles.muted}>{user.age ? `${user.age}세` : '연령 미입력'}</Text>
        <Text style={styles.muted}>{user.phone_number || '전화번호 미입력'}</Text>
        {!dashboard && <Text style={styles.muted}>프로필 정보를 불러오는 중입니다.</Text>}
      </View>
    </View>
    <View style={styles.profileMetrics}>
      <ProfileMetric value={dashboard?.total_practices ?? 0} label="누적 연습" />
      <ProfileMetric value={averageValue} label="평균 점수" />
      <ProfileMetric value={dashboard?.streak_days ?? 0} label="연속 학습" />
    </View>
    <WeeklyTrendCard trend={dashboard?.weekly_trend} />
    <PeerRankCard peerRank={dashboard?.peer_rank} />
    <BaselineCard dashboard={dashboard} levelLabel={levelLabel} />
    <View style={styles.profileActions}>
      <Pressable hitSlop={8} onPress={onEdit} style={({ pressed }) => [styles.profileActionButton, pressed && styles.buttonPressed]}><Text style={styles.profileActionText}>회원 정보 수정</Text></Pressable>
      <Pressable hitSlop={8} onPress={onLogout} style={({ pressed }) => [styles.profileLogoutButton, pressed && styles.buttonPressed]}><Text style={styles.profileLogoutText}>로그아웃</Text></Pressable>
    </View>
  </ScrollView>;
}

function ProfileEditScreen({ dashboard, onSave, onBack }) {
  const user = dashboard?.user || {};
  const [username, setUsername] = useState(user.username || user.name || dashboard?.user_name || '');
  const [age, setAge] = useState(user.age ? String(user.age) : '');
  const [phoneNumber, setPhoneNumber] = useState(user.phone_number || '');
  const [submitting, setSubmitting] = useState(false);
  const { message: toast, show: showToast } = useTransientToast();
  useEffect(() => {
    setUsername(user.username || user.name || dashboard?.user_name || '');
    setAge(user.age ? String(user.age) : '');
    setPhoneNumber(user.phone_number || '');
  }, [dashboard?.user_name, user.age, user.name, user.phone_number, user.username]);
  const submit = async () => {
    const normalizedUsername = username.trim().toLowerCase();
    const normalizedPhone = normalizePhoneNumberInput(phoneNumber);
    if (!normalizedUsername) return showToast('아이디를 입력해 주세요.');
    if (normalizedUsername.length < 4 || normalizedUsername.length > 30) return showToast('아이디는 4~30자로 입력해 주세요.');
    if (!/^[a-zA-Z0-9_.-]+$/.test(normalizedUsername)) return showToast('아이디 형식을 확인해 주세요.');
    if (age && (Number(age) < 1 || Number(age) > 120)) return showToast('연령은 1~120 사이로 입력해 주세요.');
    if (normalizedPhone && !/^01[016789]\d{7,8}$/.test(normalizedPhone)) return showToast('전화번호 형식을 확인해 주세요.');
    setSubmitting(true);
    try { await onSave({ username: normalizedUsername, age, phoneNumber: normalizedPhone }); }
    catch (error) { showToast(error.message || '회원 정보를 수정하지 못했습니다.'); }
    finally { setSubmitting(false); }
  };
  return <View style={styles.authScreen}><ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled"><TouchableOpacity onPress={onBack}><Text style={styles.back}>‹ 내 정보로 돌아가기</Text></TouchableOpacity><Text style={styles.eyebrow}>회원 정보 수정</Text><Text style={styles.title}>기본 정보를 바꿀 수 있어요</Text><View style={styles.card}><Text style={styles.label}>아이디</Text><TextInput value={username} onChangeText={setUsername} style={styles.input} placeholder="영문·숫자 4자 이상" autoCapitalize="none" autoCorrect={false} /><Text style={styles.label}>연령 (선택)</Text><TextInput value={age} onChangeText={setAge} style={styles.input} placeholder="예: 25" keyboardType="number-pad" /><Text style={styles.label}>전화번호 (선택)</Text><TextInput value={phoneNumber} onChangeText={(value) => setPhoneNumber(normalizePhoneNumberInput(value))} style={styles.input} placeholder="01012345678" keyboardType="phone-pad" /><Button text={submitting ? '저장 중…' : '수정 완료'} onPress={submit} disabled={submitting} /></View></ScrollView><TopToast message={toast} /></View>;
}

function LoginScreen({ onLogin, onSignup }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const { message: toast, show: showToast } = useTransientToast();

  const submit = async () => {
    const normalizedUsername = username.trim().toLowerCase();
    if (!normalizedUsername) return showToast('아이디를 입력해 주세요.');
    if (normalizedUsername.length < 4 || normalizedUsername.length > 30) return showToast('아이디는 4~30자로 입력해 주세요.');
    if (!/^[a-zA-Z0-9_.-]+$/.test(normalizedUsername)) return showToast('아이디 형식을 확인해 주세요.');
    if (!password) return showToast('비밀번호를 입력해 주세요.');
    if (password.length < 8) return showToast('비밀번호는 8자 이상이어야 합니다.');
    setSubmitting(true);
    try { await onLogin(normalizedUsername, password); }
    catch (error) { showToast(error.message || '로그인에 실패했습니다.'); }
    finally { setSubmitting(false); }
  };

  return <View style={styles.authScreen}>
    <ScrollView contentContainerStyle={styles.login} keyboardShouldPersistTaps="handled"><View style={styles.card}><Text style={styles.label}>아이디</Text><TextInput value={username} onChangeText={setUsername} style={styles.input} placeholder="아이디" autoCapitalize="none" autoCorrect={false} /><Text style={styles.label}>비밀번호</Text><TextInput value={password} onChangeText={setPassword} style={styles.input} placeholder="비밀번호" secureTextEntry /><Button text={submitting ? '로그인 중…' : '로그인'} onPress={submit} disabled={submitting} /><TouchableOpacity style={styles.textButton} onPress={onSignup}><Text style={styles.textButtonLabel}>처음이신가요? 회원가입</Text></TouchableOpacity></View></ScrollView>
    <TopToast message={toast} />
  </View>;
}

function SignupScreen({ onSignup, onBack }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [passwordConfirm, setPasswordConfirm] = useState('');
  const [age, setAge] = useState('');
  const [phoneNumber, setPhoneNumber] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const { message: toast, show: showToast } = useTransientToast();
  const submit = async () => {
    const normalizedUsername = username.trim().toLowerCase();
    if (!normalizedUsername) return showToast('아이디를 입력해 주세요.');
    if (normalizedUsername.length < 4 || normalizedUsername.length > 30) return showToast('아이디는 4~30자로 입력해 주세요.');
    if (!/^[a-zA-Z0-9_.-]+$/.test(normalizedUsername)) return showToast('아이디 형식을 확인해 주세요.');
    if (!password) return showToast('비밀번호를 입력해 주세요.');
    if (password.length < 8) return showToast('비밀번호는 8자 이상이어야 합니다.');
    if (password !== passwordConfirm) return showToast('비밀번호가 서로 다릅니다.');
    if (/^\d+$/.test(password)) return showToast('비밀번호는 숫자로만 구성할 수 없습니다.');
    if (age && (Number(age) < 1 || Number(age) > 120)) return showToast('연령은 1~120 사이로 입력해 주세요.');
    setSubmitting(true);
    try { await onSignup({ username: normalizedUsername, password, age, phoneNumber: normalizePhoneNumberInput(phoneNumber) }); }
    catch (error) { showToast(error.message || '회원가입에 실패했습니다.'); }
    finally { setSubmitting(false); }
  };
  return <View style={styles.authScreen}><ScrollView contentContainerStyle={styles.authForm} keyboardShouldPersistTaps="handled"><TouchableOpacity onPress={onBack}><Text style={styles.back}>‹ 로그인으로 돌아가기</Text></TouchableOpacity><Text style={styles.title}>회원가입</Text><Text style={styles.subtitle}>아이디로 로그인하며 연령과 전화번호는 선택 입력입니다.</Text><View style={styles.card}><Text style={styles.label}>아이디</Text><TextInput value={username} onChangeText={setUsername} style={styles.input} placeholder="영문·숫자 4자 이상" autoCapitalize="none" autoCorrect={false} /><Text style={styles.label}>비밀번호</Text><TextInput value={password} onChangeText={setPassword} style={styles.input} placeholder="8자 이상, 숫자만 사용 불가" secureTextEntry /><Text style={styles.label}>비밀번호 확인</Text><TextInput value={passwordConfirm} onChangeText={setPasswordConfirm} style={styles.input} placeholder="비밀번호 재입력" secureTextEntry /><Text style={styles.label}>연령 (선택)</Text><TextInput value={age} onChangeText={setAge} style={styles.input} placeholder="예: 25" keyboardType="number-pad" /><Text style={styles.label}>전화번호 (선택)</Text><TextInput value={phoneNumber} onChangeText={(value) => setPhoneNumber(normalizePhoneNumberInput(value))} style={styles.input} placeholder="01012345678" keyboardType="phone-pad" /><Button text={submitting ? '가입 중…' : '가입하고 초기 평가하기'} onPress={submit} disabled={submitting} /></View></ScrollView><TopToast message={toast} /></View>;
}

function BaselineAssessmentScreen({ onSave }) {
  const [answers, setAnswers] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const complete = Object.keys(answers).length === BASELINE_QUESTIONS.length;
  const save = async (skipped) => {
    setSubmitting(true);
    try { await onSave(answers, skipped); }
    catch (error) { Alert.alert('초기 평가 저장 실패', error.message); }
    finally { setSubmitting(false); }
  };
  return <ScrollView contentContainerStyle={styles.content}><Text style={styles.eyebrow}>가입 완료 · 초기 설정</Text><Text style={styles.title}>현재 말하기 불편도를{`\n`}알려 주세요</Text><Text style={styles.subtitle}>향후 발음 변화와 개인화 추천을 비교하기 위한 자가 보고 기준값입니다. 이 결과는 의료 진단이나 구음장애 중증도 판정이 아닙니다.</Text>{BASELINE_QUESTIONS.map((question, index) => <View key={question.id} style={styles.assessmentCard}><Text style={styles.questionNumber}>{index + 1} / {BASELINE_QUESTIONS.length}</Text><Text style={styles.questionText}>{question.text}</Text><View style={styles.optionList}>{BASELINE_OPTIONS.map((option) => <TouchableOpacity key={option.value} style={[styles.option, answers[question.id] === option.value && styles.optionActive]} onPress={() => setAnswers((current) => ({ ...current, [question.id]: option.value }))}><Text style={[styles.optionText, answers[question.id] === option.value && styles.optionTextActive]}>{option.label}</Text><Text style={[styles.optionScore, answers[question.id] === option.value && styles.optionTextActive]}>{option.value}</Text></TouchableOpacity>)}</View></View>)}<Button text={submitting ? '저장 중…' : '평가 저장하고 시작하기'} onPress={() => save(false)} disabled={!complete || submitting} /><TouchableOpacity style={styles.skipButton} disabled={submitting} onPress={() => save(true)}><Text style={styles.skipButtonText}>나중에 할게요 · 건너뛰기</Text></TouchableOpacity></ScrollView>;
}

function Chips({ values, selected, onChange }) { return <View style={styles.chips}>{values.map((value) => <Pressable key={value} hitSlop={6} style={[styles.chip, value === selected && styles.chipActive]} onPress={() => onChange(value)}><Text style={[styles.chipText, value === selected && styles.chipTextActive]}>{value}</Text></Pressable>)}</View>; }
function Badge({ text }) { return <View style={styles.badge}><Text style={styles.badgeText}>{text}</Text></View>; }
function Button({ text, onPress, disabled, danger }) { return <Pressable disabled={disabled} hitSlop={8} onPress={onPress} style={({ pressed }) => [styles.button, danger && styles.dangerButton, disabled && styles.disabled, pressed && !disabled && styles.buttonPressed]}><Text style={styles.buttonText}>{text}</Text><Text style={styles.buttonText}>→</Text></Pressable>; }
function Stat({ value, label }) { return <View style={styles.stat}><Text style={styles.statValue}>{value}</Text><Text style={styles.muted}>{label}</Text></View>; }
function BottomNav({ screen, onNavigate }) {
  const items = [
    { id: 'select', Icon: House, label: '홈' },
    { id: 'lifestyle', Icon: Headphones, label: '생활용' },
    { id: 'history', Icon: History, label: '기록' },
    { id: 'profile', Icon: User, label: '내 정보' },
  ];
  return <View style={styles.nav}>{items.map((item) => {
    const active = screen === item.id || (screen === 'edit-profile' && item.id === 'profile');
    return <Pressable key={item.id} hitSlop={6} style={styles.navItem} onPress={() => onNavigate(item.id)}><item.Icon size={24} strokeWidth={2.4} color={active ? COLORS.primary : COLORS.muted} /><Text style={[styles.navText, active && styles.navActive]}>{item.label}</Text></Pressable>;
  })}</View>;
}
const average = (values) => values.length ? Math.round(values.reduce((a, b) => a + b, 0) / values.length) : 0;

const styles = StyleSheet.create({
  authScreen: { flex: 1 },
  modalBackdrop: { flex: 1, padding: 24, alignItems: 'center', justifyContent: 'center', backgroundColor: 'rgba(16, 20, 38, 0.42)' },
  modalCard: { width: '100%', maxWidth: 420, padding: 20, borderRadius: 18, backgroundColor: COLORS.surface, shadowColor: '#000', shadowOpacity: 0.16, shadowRadius: 18, shadowOffset: { width: 0, height: 8 }, elevation: 14 },
  modalEyebrow: { color: COLORS.primary, fontSize: 12, fontWeight: '900', marginBottom: 8 },
  modalTitle: { color: COLORS.ink, fontSize: 24, lineHeight: 30, fontWeight: '900' },
  modalSentence: { color: COLORS.ink, fontSize: 17, lineHeight: 25, fontWeight: '800', marginTop: 14, padding: 14, borderRadius: 12, backgroundColor: COLORS.canvas },
  modalActions: { flexDirection: 'row', gap: 10, marginTop: 18 },
  modalCancel: { flex: 1, minHeight: 48, borderRadius: 12, alignItems: 'center', justifyContent: 'center', backgroundColor: COLORS.canvas, borderWidth: 1, borderColor: COLORS.line },
  modalConfirm: { flex: 1, minHeight: 48, borderRadius: 12, alignItems: 'center', justifyContent: 'center', backgroundColor: COLORS.primary },
  modalCancelText: { color: COLORS.muted, fontSize: 14, fontWeight: '900' },
  modalConfirmText: { color: '#FFF', fontSize: 14, fontWeight: '900' },
  toastLayer: { position: 'absolute', top: 14, left: 16, right: 16, zIndex: 999, elevation: 12, alignItems: 'center' },
  toast: { maxWidth: 420, paddingVertical: 10, paddingHorizontal: 16, borderRadius: 18, backgroundColor: 'rgba(30, 36, 64, 0.96)', shadowColor: '#000', shadowOpacity: 0.18, shadowRadius: 8, shadowOffset: { width: 0, height: 3 } },
  toastText: { color: '#FFF', fontSize: 13, fontWeight: '800', textAlign: 'center' },
  authForm: { flexGrow: 1, padding: 24, paddingBottom: 100 },
  textButton: { alignItems: 'center', paddingVertical: 16 },
  textButtonLabel: { color: COLORS.primary, fontWeight: '800' },
  sentenceLeftMeta: { flex: 1, flexDirection: 'row', alignItems: 'center', gap: 8, paddingRight: 8 },
  sentenceRightMeta: { flexDirection: 'row', alignItems: 'center', justifyContent: 'flex-end', gap: 8 },
  sentenceScoreText: { color: COLORS.primary, fontSize: 12, lineHeight: 18, fontWeight: '900' },
  ttsHint: { color: COLORS.muted, fontSize: 12, lineHeight: 18, marginTop: 10, textAlign: 'center' },
  profileContent: { padding: 20, paddingBottom: 104 },
  profileHeader: { marginBottom: 12 },
  profileHero: { minHeight: 118, flexDirection: 'row', alignItems: 'center', gap: 14 },
  profileAvatar: { width: 62, height: 62, borderRadius: 31, alignItems: 'center', justifyContent: 'center', backgroundColor: COLORS.soft, borderWidth: 1, borderColor: '#DCDDFF' },
  profileAvatarText: { color: COLORS.primary, fontSize: 24, fontWeight: '900' },
  profileHeroBody: { flex: 1, gap: 3 },
  profileMetrics: { flexDirection: 'row', gap: 8, marginBottom: 10 },
  profileMetric: { flex: 1, minHeight: 86, borderRadius: 14, backgroundColor: COLORS.surface, borderWidth: 1, borderColor: COLORS.line, alignItems: 'center', justifyContent: 'center', padding: 8 },
  profileMetricValue: { color: COLORS.primary, fontSize: 24, lineHeight: 30, fontWeight: '900' },
  profileMetricLabel: { color: COLORS.muted, fontSize: 11, lineHeight: 15, fontWeight: '800', textAlign: 'center' },
  profileCompareCard: { padding: 18 },
  profileCompareHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 14 },
  profileCompareMain: { flex: 1 },
  profileRank: { color: COLORS.primary, fontSize: 28, lineHeight: 34, fontWeight: '900', marginBottom: 2 },
  profileRankBadge: { minWidth: 76, minHeight: 70, borderRadius: 16, alignItems: 'center', justifyContent: 'center', backgroundColor: COLORS.soft, borderWidth: 1, borderColor: '#DCDDFF' },
  profileRankBadgeText: { color: COLORS.primary, fontSize: 22, lineHeight: 26, fontWeight: '900' },
  profileRankBadgeSub: { color: COLORS.muted, fontSize: 11, fontWeight: '800' },
  profileEncouragement: { color: COLORS.success, fontSize: 13, lineHeight: 20, fontWeight: '800', marginTop: 14 },
  weeklyTrendCard: { padding: 18 },
  weeklyTrendTitle: { color: COLORS.ink, fontSize: 20, lineHeight: 27, fontWeight: '900', marginBottom: 4 },
  weeklyScoreStack: { minWidth: 74, minHeight: 70, borderRadius: 16, alignItems: 'center', justifyContent: 'center', backgroundColor: '#E9F8F1', borderWidth: 1, borderColor: '#CBECDD' },
  weeklyScoreValue: { color: COLORS.success, fontSize: 24, lineHeight: 29, fontWeight: '900' },
  weeklyScoreLabel: { color: COLORS.success, fontSize: 11, fontWeight: '900' },
  profileBaselineText: { color: COLORS.ink, fontSize: 18, lineHeight: 25, fontWeight: '900', marginBottom: 5 },
  profileActions: { flexDirection: 'row', gap: 10, marginTop: 4 },
  profileActionButton: { flex: 1, minHeight: 52, borderRadius: 14, alignItems: 'center', justifyContent: 'center', backgroundColor: COLORS.primary },
  profileActionText: { color: '#FFF', fontSize: 14, fontWeight: '900' },
  profileLogoutButton: { flex: 1, minHeight: 52, borderRadius: 14, alignItems: 'center', justifyContent: 'center', backgroundColor: '#FFF0F1', borderWidth: 1, borderColor: '#F3C3C8' },
  profileLogoutText: { color: COLORS.danger, fontSize: 14, fontWeight: '900' },
  profileEditPill: { alignSelf: 'flex-start', marginTop: 14, paddingVertical: 8, paddingHorizontal: 12, borderRadius: 999, backgroundColor: COLORS.soft, borderWidth: 1, borderColor: '#DCDDFF' },
  profileEditText: { color: COLORS.primary, fontSize: 12, fontWeight: '900' },
  assessmentCard: { backgroundColor: COLORS.surface, borderRadius: 16, borderWidth: 1, borderColor: COLORS.line, padding: 16, marginBottom: 12 },
  questionNumber: { color: COLORS.primary, fontSize: 11, fontWeight: '900' },
  questionText: { color: COLORS.ink, fontSize: 16, lineHeight: 23, fontWeight: '800', marginTop: 7, marginBottom: 12 },
  optionList: { gap: 7 },
  option: { minHeight: 42, paddingHorizontal: 13, borderRadius: 11, borderWidth: 1, borderColor: COLORS.line, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  optionActive: { borderColor: COLORS.primary, backgroundColor: COLORS.soft },
  optionText: { color: COLORS.muted, fontSize: 13, fontWeight: '700' },
  optionScore: { color: COLORS.muted, fontSize: 12, fontWeight: '900' },
  optionTextActive: { color: COLORS.primary },
  skipButton: { alignItems: 'center', paddingVertical: 18, marginBottom: 24 },
  skipButtonText: { color: COLORS.muted, fontWeight: '800' },
  customSentenceInput: { minHeight: 96, marginTop: 14, paddingTop: 12, textAlignVertical: 'top' },
  customLevelRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  customLevel: { minHeight: 40, paddingHorizontal: 13, borderRadius: 20, borderWidth: 1, borderColor: COLORS.line, alignItems: 'center', justifyContent: 'center', backgroundColor: COLORS.surface },
  customLevelActive: { borderColor: COLORS.primary, backgroundColor: COLORS.soft },
  buttonPressed: { transform: [{ scale: 0.985 }], opacity: 0.86 },
  errorFeedbackTitle: { color: '#7F2631', fontWeight: '800', marginTop: 9 },
  errorFeedback: { color: '#9B3541', fontSize: 12, lineHeight: 18, marginTop: 4 },
  errorWordBox: { marginTop: 10, padding: 11, borderRadius: 12, backgroundColor: '#FFFFFF', borderWidth: 1, borderColor: '#F3C3C8' },
  errorWordLabel: { color: COLORS.muted, fontSize: 11, fontWeight: '900', marginBottom: 5 },
  errorWordText: { color: COLORS.ink, fontSize: 22, lineHeight: 30, fontWeight: '900' },
  errorWordPlain: { color: COLORS.ink, fontWeight: '900' },
  errorWordMarked: { color: COLORS.danger, fontWeight: '900', backgroundColor: '#FFE1E5' },
  errorUnitTitle: { color: COLORS.ink, fontSize: 15, lineHeight: 21, fontWeight: '900' },
  errorWordSyllables: { flexDirection: 'row', flexWrap: 'wrap', gap: 7 },
  errorSyllableChip: { minWidth: 54, paddingVertical: 8, paddingHorizontal: 10, borderRadius: 12, alignItems: 'center', backgroundColor: COLORS.canvas, borderWidth: 1, borderColor: COLORS.line },
  errorSyllableChipMarked: { backgroundColor: '#FFE1E5', borderColor: COLORS.danger },
  errorSyllableText: { color: COLORS.ink, fontSize: 22, lineHeight: 27, fontWeight: '900' },
  errorSyllableTextMarked: { color: COLORS.danger },
  errorSyllableIpa: { color: COLORS.muted, fontSize: 10, lineHeight: 14, fontWeight: '800', marginTop: 2 },
  errorSyllableIpaMarked: { color: COLORS.danger },
  limitedNotice: { color: COLORS.muted, fontSize: 12, lineHeight: 18, textAlign: 'center', paddingVertical: 10, paddingHorizontal: 12 },
  articulationScroll: { marginTop: 8, flexShrink: 1 },
  articulationScrollContent: { paddingBottom: 8 },
  analysisModal: { maxWidth: 430, alignItems: 'center' },
  analysisModalTitle: { color: COLORS.ink, fontSize: 22, lineHeight: 28, fontWeight: '900', textAlign: 'center', marginTop: 16 },
  analysisModalText: { color: COLORS.muted, fontSize: 13, lineHeight: 20, textAlign: 'center', marginTop: 9 },
  analysisAppealBox: { width: '100%', marginTop: 16, padding: 14, borderRadius: 14, backgroundColor: COLORS.soft, borderWidth: 1, borderColor: '#DCDDFF' },
  analysisAppealItem: { color: COLORS.ink, fontSize: 12, lineHeight: 19, fontWeight: '700', marginBottom: 5 },
  referenceBox: { marginTop: 14, padding: 13, borderRadius: 14, backgroundColor: '#F8FAFC', borderWidth: 1, borderColor: COLORS.line },
  referenceTitle: { color: COLORS.ink, fontSize: 12, fontWeight: '900', marginBottom: 7 },
  referenceItem: { paddingVertical: 7, borderTopWidth: 1, borderColor: '#E9ECF4' },
  referenceName: { color: COLORS.ink, fontSize: 11, lineHeight: 16, fontWeight: '900' },
  referenceText: { color: COLORS.muted, fontSize: 11, lineHeight: 16, marginTop: 2 },
  referenceUrl: { color: COLORS.primary, fontSize: 10, lineHeight: 15, fontWeight: '800', marginTop: 7 },
  transitionCanvas: { height: 240, marginTop: 10, borderRadius: 14, backgroundColor: '#FFFFFF', overflow: 'hidden', borderWidth: 1, borderColor: COLORS.line },
  transitionImage: { borderRadius: 14, opacity: 0.72, transform: [{ scale: 1.32 }, { translateX: -58 }, { translateY: -4 }] },
  tongueImage: { borderRadius: 14, opacity: 0.2, transform: [{ scale: 1.36 }, { translateX: -62 }, { translateY: -4 }] },
  transitionLegend: { flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'center', gap: 12, marginTop: 10 },
  userDot: { backgroundColor: COLORS.danger },
  targetDot: { backgroundColor: COLORS.primary },
  ruleStatsCard: { padding: 16, borderRadius: 16, backgroundColor: COLORS.surface, borderWidth: 1, borderColor: COLORS.line },
  ruleStatsTitle: { color: COLORS.ink, fontSize: 16, lineHeight: 22, fontWeight: '900' },
  ruleStatsBadge: { minWidth: 58, minHeight: 58, borderRadius: 14, alignItems: 'center', justifyContent: 'center', backgroundColor: '#FFF0F1', borderWidth: 1, borderColor: '#F3C3C8' },
  ruleStatsBadgeText: { color: COLORS.danger, fontSize: 22, lineHeight: 26, fontWeight: '900' },
  ruleStatsBadgeSub: { color: COLORS.danger, fontSize: 11, fontWeight: '900' },
  ruleStatsList: { gap: 10, marginTop: 14 },
  ruleStatsRow: { gap: 6 },
  ruleStatsName: { color: COLORS.ink, fontSize: 13, fontWeight: '900' },
  ruleStatsCount: { color: COLORS.primary, fontSize: 12, fontWeight: '900' },
  ruleStatsTrack: { height: 8, borderRadius: 999, backgroundColor: COLORS.soft, overflow: 'hidden' },
  ruleStatsBar: { height: 8, borderRadius: 999, backgroundColor: COLORS.primary },
  ruleStatsHint: { color: COLORS.muted, fontSize: 12, lineHeight: 18, marginTop: 12 },
  splash: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: COLORS.canvas }, splashLogo: { color: COLORS.primary, fontSize: 30, fontWeight: '900' }, safe: { flex: 1, backgroundColor: COLORS.canvas }, frame: { flex: 1, width: '100%', maxWidth: 680, alignSelf: 'center' }, header: { height: 64, paddingHorizontal: 20, backgroundColor: COLORS.surface, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', borderBottomWidth: 1, borderColor: COLORS.line }, logo: { fontSize: 18, fontWeight: '900', color: COLORS.primary }, headerText: { fontSize: 12, fontWeight: '700', color: COLORS.success }, content: { padding: 20, paddingBottom: 100 }, login: { flexGrow: 1, padding: 24, paddingBottom: 100, justifyContent: 'center' }, eyebrow: { color: COLORS.primary, fontWeight: '900', marginTop: 6, marginBottom: 7 }, title: { color: COLORS.ink, fontSize: 28, lineHeight: 36, fontWeight: '900' }, subtitle: { color: COLORS.muted, lineHeight: 20, marginTop: 10, marginBottom: 18 }, label: { fontSize: 12, color: COLORS.muted, fontWeight: '800', marginTop: 12, marginBottom: 7 }, sectionTitle: { fontSize: 17, fontWeight: '900', color: COLORS.ink, marginTop: 20, marginBottom: 10 }, chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 7 }, chip: { paddingVertical: 8, paddingHorizontal: 12, borderRadius: 20, borderWidth: 1, borderColor: COLORS.line, backgroundColor: COLORS.surface }, chipActive: { backgroundColor: COLORS.soft, borderColor: COLORS.primary }, chipText: { color: COLORS.muted, fontWeight: '700', fontSize: 12 }, chipTextActive: { color: COLORS.primary }, card: { backgroundColor: COLORS.surface, borderRadius: 16, borderWidth: 1, borderColor: COLORS.line, padding: 16, marginBottom: 10 }, cardActive: { borderWidth: 2, borderColor: COLORS.primary }, rowBetween: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }, sentenceMeta: { flexDirection: 'row', alignItems: 'center', gap: 8 }, deletePill: { paddingVertical: 5, paddingHorizontal: 9, borderRadius: 999, backgroundColor: '#FFF0F1', borderWidth: 1, borderColor: '#F3C3C8' }, deletePillText: { color: COLORS.danger, fontSize: 11, fontWeight: '900' }, badge: { alignSelf: 'flex-start', paddingVertical: 4, paddingHorizontal: 8, borderRadius: 8, backgroundColor: COLORS.soft }, badgeText: { color: COLORS.primary, fontSize: 11, fontWeight: '800' }, sentence: { color: COLORS.ink, fontSize: 18, lineHeight: 26, fontWeight: '800', marginTop: 10 }, ipa: { color: COLORS.muted, fontSize: 12, lineHeight: 18, marginTop: 8 }, reason: { color: COLORS.success, fontSize: 12, marginTop: 10, fontWeight: '700' }, muted: { color: COLORS.muted, fontSize: 12 }, button: { minHeight: 54, paddingHorizontal: 18, borderRadius: 15, backgroundColor: COLORS.primary, marginTop: 16, flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }, dangerButton: { backgroundColor: COLORS.danger }, disabled: { opacity: .5 }, buttonText: { color: '#FFF', fontSize: 15, fontWeight: '900' }, notice: { backgroundColor: '#FFF5D9', paddingHorizontal: 20, paddingVertical: 10 }, noticeText: { color: COLORS.warning, fontSize: 12, fontWeight: '700' }, back: { color: COLORS.muted, fontWeight: '700', marginBottom: 16 }, practice: { backgroundColor: COLORS.soft, padding: 17, borderRadius: 16, marginTop: 20, marginBottom: 15 }, hintToggle: { minHeight: 42, marginTop: 14, borderRadius: 12, paddingHorizontal: 12, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', backgroundColor: COLORS.surface, borderWidth: 1, borderColor: COLORS.line }, hintToggleText: { color: COLORS.primary, fontSize: 13, fontWeight: '900' }, hintToggleIcon: { color: COLORS.primary, fontSize: 18, fontWeight: '900' }, ipaHint: { color: COLORS.muted, fontSize: 13, lineHeight: 20, marginTop: 10, padding: 12, borderRadius: 12, backgroundColor: 'rgba(255,255,255,0.72)' }, recordBox: { alignItems: 'center', padding: 24, borderRadius: 20, backgroundColor: COLORS.surface, borderWidth: 1, borderColor: COLORS.line }, webFilePicker: { marginTop: 12, padding: 14, borderRadius: 14, backgroundColor: COLORS.surface, borderWidth: 1, borderStyle: 'dashed', borderColor: COLORS.line }, webFilePickerLabel: { color: COLORS.primary, fontSize: 12, fontWeight: '900', marginTop: 8 }, consentRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 12, marginTop: 12, padding: 14, borderRadius: 14, backgroundColor: COLORS.surface, borderWidth: 1, borderColor: COLORS.line }, consentText: { flex: 1 }, recording: { borderColor: '#F3C3C8', backgroundColor: '#FFFAFA' }, recordState: { color: COLORS.danger, fontWeight: '900' }, timer: { fontVariant: ['tabular-nums'], fontSize: 38, color: COLORS.ink, fontWeight: '900', marginVertical: 20 }, mic: { width: 76, height: 76, borderRadius: 38, alignItems: 'center', justifyContent: 'center', backgroundColor: COLORS.primary, marginBottom: 14 }, micLive: { backgroundColor: COLORS.danger }, micText: { color: '#FFF', fontSize: 27 }, scoreCard: { padding: 22, borderRadius: 20, marginTop: 18, backgroundColor: COLORS.primary }, score: { color: '#FFF', fontSize: 53, fontWeight: '900' }, scoreUnit: { fontSize: 19 }, scoreCaption: { color: '#DCDDFF', marginTop: 6, fontWeight: '700' }, ipaCard: { backgroundColor: COLORS.surface, borderWidth: 1, borderColor: COLORS.line, borderRadius: 14, padding: 14, marginBottom: 9 }, ipaCardActive: { borderColor: COLORS.primary, backgroundColor: COLORS.soft }, ipaTokens: { flexDirection: 'row', flexWrap: 'wrap' }, token: { color: COLORS.ink, fontSize: 15, fontWeight: '700' }, errorToken: { color: COLORS.danger, fontWeight: '900' }, errorRow: { backgroundColor: '#FFF0F1', borderRadius: 12, padding: 12, marginBottom: 7 }, visualHint: { color: COLORS.primary, fontSize: 12, fontWeight: '900' }, errorDescription: { color: '#9B3541', fontSize: 12, marginTop: 5 }, feedback: { backgroundColor: '#E9F8F1', padding: 16, borderRadius: 16, marginTop: 18 }, feedbackTitle: { color: COLORS.success, fontWeight: '900', fontSize: 15 }, feedbackText: { color: '#27634E', lineHeight: 20, marginTop: 7 }, priority: { color: COLORS.success, fontWeight: '800', marginTop: 9 }, articulationModal: { maxWidth: 520, maxHeight: '92%' }, articulationLead: { color: COLORS.muted, fontSize: 12, lineHeight: 18, marginTop: 12 }, closePill: { paddingVertical: 7, paddingHorizontal: 11, borderRadius: 999, backgroundColor: COLORS.canvas, borderWidth: 1, borderColor: COLORS.line }, closePillText: { color: COLORS.muted, fontSize: 12, fontWeight: '900' }, ipaFlow: { marginTop: 12 }, ipaFlowTokens: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 }, ipaFlowToken: { minWidth: 32, paddingVertical: 6, paddingHorizontal: 9, borderRadius: 999, backgroundColor: COLORS.canvas, alignItems: 'center' }, ipaFlowText: { color: COLORS.ink, fontSize: 13, fontWeight: '800' }, ipaFlowTextActive: { color: '#FFF' }, articulationPanel: { marginTop: 12, padding: 12, borderRadius: 16, backgroundColor: COLORS.canvas, borderWidth: 1, borderColor: COLORS.line }, articulationTitle: { color: COLORS.ink, fontSize: 15, fontWeight: '900' }, tongueCanvas: { height: 190, marginTop: 8, borderRadius: 14, backgroundColor: '#F8FAFC', overflow: 'hidden' }, articulationLabel: { color: COLORS.ink, fontSize: 14, fontWeight: '900', marginTop: 8 }, articulationDescription: { color: COLORS.muted, fontSize: 12, lineHeight: 18, marginTop: 4 }, compareBox: { marginTop: 12, padding: 13, borderRadius: 14, backgroundColor: '#EEF0FF' }, compareTitle: { color: COLORS.primary, fontSize: 13, fontWeight: '900' }, compareText: { color: COLORS.ink, fontSize: 12, lineHeight: 18, marginTop: 5 }, stats: { flexDirection: 'row', gap: 8, marginTop: 20 }, stat: { flex: 1, minHeight: 82, borderRadius: 14, backgroundColor: COLORS.surface, borderWidth: 1, borderColor: COLORS.line, alignItems: 'center', justifyContent: 'center', padding: 8 }, statValue: { fontSize: 22, fontWeight: '900', color: COLORS.primary }, chart: { minHeight: 155, padding: 16, borderRadius: 16, backgroundColor: COLORS.surface, flexDirection: 'row', gap: 10, alignItems: 'flex-end', borderWidth: 1, borderColor: COLORS.line }, bar: { flex: 1, backgroundColor: '#A8ACFF', borderRadius: 6, justifyContent: 'flex-start', alignItems: 'center' }, barText: { color: COLORS.primary, fontSize: 10, fontWeight: '800', marginTop: -16 }, histogramCard: { minHeight: 190, padding: 16, borderRadius: 16, backgroundColor: COLORS.surface, borderWidth: 1, borderColor: COLORS.line }, histogramLegend: { flexDirection: 'row', justifyContent: 'flex-end', gap: 14, marginBottom: 12 }, legendItem: { flexDirection: 'row', alignItems: 'center', gap: 5 }, legendDot: { width: 9, height: 9, borderRadius: 5 }, countDot: { backgroundColor: '#8B7CFF' }, scoreDot: { backgroundColor: '#38A169' }, histogramBody: { height: 148, flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-end' }, histogramGroup: { flex: 1, alignItems: 'center', marginHorizontal: 8 }, histogramBars: { height: 124, flexDirection: 'row', alignItems: 'flex-end', gap: 4 }, histogramBar: { width: 18, borderTopLeftRadius: 7, borderTopRightRadius: 7, alignItems: 'center', justifyContent: 'flex-start' }, countBar: { backgroundColor: '#8B7CFF' }, scoreBar: { backgroundColor: '#38A169' }, histogramValue: { color: '#FFF', fontSize: 9, fontWeight: '900', marginTop: 3 }, histogramLabel: { color: COLORS.ink, fontSize: 12, fontWeight: '900', marginTop: 8 }, history: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingVertical: 13, borderBottomWidth: 1, borderColor: COLORS.line }, historyBody: { flex: 1, paddingRight: 12 }, historySentence: { color: COLORS.ink, fontWeight: '800' }, historyScore: { color: COLORS.primary, fontWeight: '900' }, boxPlotCard: { backgroundColor: COLORS.surface, borderRadius: 16, borderWidth: 1, borderColor: COLORS.line, padding: 16, marginBottom: 10 }, boxPlotTitle: { color: COLORS.ink, fontSize: 16, fontWeight: '900' }, boxPlotAverage: { color: COLORS.primary, fontSize: 13, fontWeight: '900' }, boxPlotTrack: { position: 'relative', height: 36, marginTop: 16, marginHorizontal: 4, justifyContent: 'center' }, boxPlotWhisker: { position: 'absolute', height: 3, borderRadius: 3, backgroundColor: '#A8ACFF', top: 16 }, boxPlotBox: { position: 'absolute', height: 20, borderRadius: 7, backgroundColor: COLORS.soft, borderWidth: 2, borderColor: COLORS.primary, top: 7 }, boxPlotMedian: { position: 'absolute', width: 3, height: 26, borderRadius: 2, backgroundColor: COLORS.primary, top: 4 }, boxPlotAverageDot: { position: 'absolute', width: 10, height: 10, borderRadius: 5, backgroundColor: COLORS.danger, top: 12, marginLeft: -4 }, boxPlotScale: { flexDirection: 'row', justifyContent: 'space-between', marginTop: 2 }, profileName: { color: COLORS.ink, fontWeight: '900', fontSize: 20 }, api: { color: COLORS.muted, fontSize: 11, marginTop: 24 }, input: { height: 50, borderWidth: 1, borderColor: COLORS.line, borderRadius: 12, paddingHorizontal: 13, color: COLORS.ink, backgroundColor: '#FCFCFE' }, empty: { color: COLORS.muted, paddingVertical: 16, textAlign: 'center' }, center: { flex: 1, alignItems: 'center', justifyContent: 'center' }, nav: { position: 'absolute', bottom: 0, left: 0, right: 0, height: 72, paddingHorizontal: 8, backgroundColor: COLORS.surface, flexDirection: 'row', borderTopWidth: 1, borderColor: COLORS.line }, navItem: { flex: 1, gap: 3, alignItems: 'center', justifyContent: 'center' }, navText: { fontSize: 11, lineHeight: 14, textAlign: 'center', fontWeight: '800', color: COLORS.muted }, navActive: { color: COLORS.primary }
});

export default App;
