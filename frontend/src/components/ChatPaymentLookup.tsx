import { useEffect, useState } from 'react';
import type { ConversationMessage } from '../api/types';
import { canonical, useLanguage } from '../i18n';
import { detectIntent } from '../demo';
import type { Turn } from '../demo';
import { amountFromQuestion } from '../paymentDemo';
import { CounterPayment } from './MerchantChecks';
import { replyDelay } from './ResponseActivity';

// A read-only sample lookup, separate from backend task execution and receipts.
export function ChatPaymentLookup({
  messages,
  index,
}: {
  messages: ConversationMessage[];
  index: number;
}) {
  const message = messages[index];
  const question = messages[index - 1];
  if (message.role !== 'assistant' || question?.role !== 'user') return null;
  const intent = detectIntent(canonical(question.content));
  const previousQuestion = messages
    .slice(0, index - 1)
    .reverse()
    .find((item) => item.role === 'user');
  const followsPaymentQuestion =
    intent === 'other' &&
    amountFromQuestion(question.content) &&
    previousQuestion &&
    detectIntent(canonical(previousQuestion.content)) === 'counter';
  if (intent !== 'counter' && !followsPaymentQuestion) return null;
  return (
    <PaymentLookup key={question.message_id} id={question.message_id} question={question.content} />
  );
}

function PaymentLookup({ id, question }: { id: string; question: string }) {
  const { t } = useLanguage();
  const [turn, setTurn] = useState<Turn>(() => {
    const amount = amountFromQuestion(question);
    const started = Date.now();
    return {
      id,
      question,
      intent: 'counter',
      started,
      offer: '',
      counterQuery: amount ? { amount, minutes: 15, checkedAt: started } : undefined,
    };
  });
  const [now, setNow] = useState(Date.now);
  const [reduced, setReduced] = useState(
    () => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false,
  );
  useEffect(() => {
    const media = window.matchMedia?.('(prefers-reduced-motion: reduce)');
    const update = () => setReduced(media?.matches ?? false);
    media?.addEventListener('change', update);
    return () => media?.removeEventListener('change', update);
  }, []);
  useEffect(() => {
    if (!turn.counterQuery) return;
    const started = turn.counterQuery.checkedAt;
    const timer = window.setInterval(() => {
      const timestamp = Date.now();
      setNow(timestamp);
      if (timestamp - started >= replyDelay) window.clearInterval(timer);
    }, 100);
    return () => window.clearInterval(timer);
  }, [turn.counterQuery?.checkedAt]);
  return (
    <section className="chat-payment-lookup" aria-label={t('Sample payment lookup')}>
      <p className="fine payment-sample-label">
        {t('Sample payment records · Customer names and times are simulated.')}
      </p>
      <CounterPayment
        turn={turn}
        now={now}
        reduced={reduced}
        update={(change) => {
          setNow(Date.now());
          setTurn((previous) => ({ ...previous, ...change }));
        }}
      />
    </section>
  );
}
