# Blog Posts

## [👋 Welcome to Lil’Log](https://lilianweng.github.io/)

Hi, this is Lilian. I’m documenting my learning notes in this blog since 2017. Based on the number of grammar mistakes in my posts, you can tell how much ChatGPT is involved 😉.

---

## [Why We Think](https://lilianweng.github.io/posts/2025-05-01-thinking/)

Special thanks to John Schulman for a lot of super valuable feedback and direct edits on this post.

Test time compute (Graves et al. 2016, Ling, et al. 2017, Cobbe et al. 2021) and Chain-of-thought (CoT) (Wei et al. 2022, Nye et al. 2021), have led to significant improvements in model performance, while raising many research questions. This post aims to review recent developments in how to effectively use test-time compute (i.e. “thinking time”) and why it helps.

Enabling models to think for longer can be motivated in a few different ways.

The core idea is deeply connected to how humans think. We humans cannot immediately provide the answer for "What's 12345 times 56789?". Rather, it is natural to spend time pondering and analyzing before getting to the result, especially for complex problems. In Thinking, Fast and Slow (Kahneman, 2013), Daniel Kahneman characterizes human thinking into two modes, through the lens of the dual process theory :

Because System 1 thinking is fast and easy, it often ends up being the main decision driver, at the cost of accuracy and logic. It naturally relies on our brain’s mental shortcuts (i.e., heuristics) and can lead to errors and biases. By consciously slowing down and taking more time to reflect, improve and analyze, we can engage in System 2 thinking to challenge our instincts and make more rational choices.

One view of deep learning, is that neural networks can be characterized by the amount of computation and storage they can access in a forward pass, and if we optimize them to solve problems using gradient descent, the optimization process will figure out how to use these resources–they’ll figure out how to organize these resources into circuits for calculation and information storage. From this view, if we design an architecture or system that can do more computation at test time, and we train it to effectively use this resource, it’ll work better.

In Transformer models, the amount of computation (flops) that the model does for each generated token is roughly 2 times the number of parameters. For sparse models like mixture of experts (MoE), only a fraction of the parameters are used in each forward pass, so computation = 2 * parameters / sparsity, where sparsity is the fraction of experts active.

On the other hand, CoT enables the model to perform far more flops of computation for each token of the answer that it is trying to compute. In fact, CoT has a nice property that it allows the model to use a variable amount of compute depending on the hardness of the problem.

A classic idea in machine learning is to define a probabilistic model with a latent (hidden) variable $z$ and a visible variable $y$, where $y$ is given to our learning algorithm. Marginalizing (summing) over the possible values of the latent variable allows us to express a rich distribution over the visible variables, $P(y) = \sum_{z \sim P(z)} P(y \mid z)$. For example, we can model the distribution over math problems and solutions by letting $x$ denote a problem statement, $y$ be ground truth answer or proof, and $z$ as a free-form thought process that leads to the proof. The marginal probability distribution to optimize would be $P(y \mid x) = \sum_{z \sim p(z\mid x)} P(y \mid x, z)$

The latent variable perspective is particularly useful for understanding methods that involve collecting multiple parallel CoTs or searching over the CoT–these algorithms can be seen as sampling from the posterior $P(z \mid x, y)$. This view also suggests the benefits of using the log loss $\log P(y \mid x)$ as the target objective to optimize, as the log loss objective has been so effective in pretraining.

The strategy of generating intermediate steps before generating short answers, particularly for math problems, was explored by Ling, et al. 2017, who introduced the AQUA-RAT dataset, and then expanded by Cobbe et al. 2021, who introduced the Grade School Math (GSM) dataset. Cobbe et al. train a generator with supervised learning on human-written solutions and verifiers that predict the correctness of a candidate solution; they can then search over these solutions. Nye et al. (2021) experimented with intermediate thinking tokens as “scratchpads” and Wei et al. (2022) coined the now-standard term chain-of-thought (CoT).

Early work on improving CoT reasoning involved doing supervised learning on human-written reasoning traces or model-written traces filtered for answer correctness, where the latter can be seen as a rudimentary form of reinforcement learning (RL). Some other work found that one could significantly boost math performance of instruction tuned models by prompting them appropriately, with "think step by step" (Kojima et al. 2022) or more complex prompting to encourage the model to reflect on related knowledge first (Yasunaga et al. 2023).

Later work found that the CoT reasoning capabilities can be significantly improved by doing reinforcement learning on a dataset of problems with automatically checkable solutions, such as STEM problems with short answers, or coding tasks that can be checked with unit tests (Zelikman et al. 2022, Wang et al., 2023, Liu et al., 2023). This approach rose to prominence with the announcement of o1-preview, o3, and the R1 tech report (DeepSeek-AI, 2025), which showed that a simple recipe where a policy gradient algorithm could lead to strong performance.

The fundamental intent of test-time compute is to adaptively modify the model’s output distribution at test time. There are various ways of utilizing test time resources for decoding to select better samples and thus alter the model’s predictions towards a more desired distribution. Two main approaches for improving the decoding process are parallel sampling and sequential revision.

Parallel sampling is simple, intuitive and easier to implement, but bounded by the model capability of whether it can achieve the correct solution in one-go. Sequential explicitly asks the model to reflect on mistakes but it is slower and requires extra care during implementation as it does run the risk of correct predictions being modified to be incorrect or introducing other types of hallucinations. These two methods can be used together. Snell et al. (2024) showed that easier questions benefit from purely sequential test-time compute, whereas harder questions often perform best with an optimal ratio of sequential to parallel compute.

Given a generative model and a scoring function that we can use to score full or partial samples, there are various search algorithms we can use to find a high scoring sample. Best-of-$N$ is the simplest such algorithm: one just collects $N$ independent samples and chooses the highest-ranking sample according to some scoring function. Beam search is a more sophisticated search algorithm that makes the search process more adaptive, spending more sampling computation on more promising parts of the solution space.

Beam search maintains a set of promising partial sequences and alternates between extending them and pruning the less promising ones. As a selection mechanism, we can use a process reward model (PRM; Lightman et al. 2023) to guide beam search candidate selection. Xie et al. (2023) used LLM to evaluate how likely its own generated reasoning step is correct, formatted as a multiple-choice question and found that per-step self-evaluation reduces accumulative errors in multi-step reasoning during beam search decoding. Besides, during sampling, annealing the temperature helps mitigate aggregated randomness. These experiments by Xie et al. achieved 5-6% improvement on few-shot GSM8k, AQuA and StrategyQA benchmarks with the Codex model. Reward balanced search (short for “REBASE”; Wu et al. 2025) separately trained a process reward model (PRM) to determine how much each node should be expanded at each depth during beam search, according to the softmax-normalized reward scores. Jiang et al. (2024) trained their PRM, named “RATIONALYST”, for beam search guidance on synthetic rationales conditioned on a large amount of unlabelled data. Good rationales are filtered based on whether they help reduce the neg log-prob of true answer tokens by a threshold, when comparing the difference between when the rationales is included in the context vs not. At inference time, RATIONALYST provides process supervision to the CoT generator by helping estimate log-prob of next reasoning steps (“implicit”) or directly generating next reasoning steps as part of the prompt (“explicit”).

Interestingly, it is possible to trigger the emergent chain-of-thought reasoning paths without explicit zero-shot or few-shot prompting. Wang & Zhou (2024) discovered that if we branch out at the first sampling tokens by retaining the top $k$ tokens with highest confidence, measured as the difference between top-1 and top-2 candidates during sampling, and then continue these $k$ sampling trials with greedy decoding onward, many of these sequences natively contain CoT. Especially when CoT does appear in the context, it leads to a more confident decoding of the final answer. To calculate the confidence of the final answer, the answer span needs to be identified by task-specific heuristics (e.g. last numerical values for math questions) or by prompting the model further with "So the answer is". The design choice of only branching out at the first token is based on the observation that early branching significantly enhances the diversity of potential paths, while later tokens are influenced a lot by previous sequences.

If the model can reflect and correct mistakes in past responses, we would expect the model to produce a nice sequence of iterative revision with increasing quality. However, this self-correction capability turns out to not exist intrinsically among LLMs and does not easily work out of the box, due to various failure modes, such as, (1) hallucination, including modifying correct responses to be incorrect; (2) behavior collapse to non-correcting behavior; e.g. making minor or no modification on the first incorrect responses; or (3) fail to generalize to distribution shift at test time. Experiments by Huang et al. (2024) showed that naively applying self-correction leads to worse performance and external feedback is needed for models to self improve, which can be based on matching ground truths, heuristics and task-specific metrics, unit tests results for coding questions (Shinn, et al. 2023), a stronger model (Zhang et al. 2024), as well as human feedback (Liu et al. 2023).

Self-correction learning (Welleck et al. 2023) aims to train a corrector model $P_\theta(y \mid y_0, x)$ given a fixed generator model $P_0(y_0 \mid x)$. While the generator model remains to be generic, the corrector model can task-specific and only does generation conditioned on an initial model response and additional feedback (e.g. a sentence, a compiler trace, unit test results; can be optional):

Recursive inspection (Qu et al. 2024) also aims to train a better corrector model but with a single model to do both generation and self-correction.

SCoRe (Self-Correction via Reinforcement Learning; Kumar et al. 2024) is a multi-turn RL approach to encourage the model to do self-correction by producing better answers at the second attempt than the one created at the first attempt. It composes two stages of training: stage 1 only maximizes the accuracy of the second attempt while enforcing a KL penalty only on the first attempt to avoid too much shifting of the first-turn responses from the base model behavior; stage 2 optimizes the accuracy of answers produced by both the first and second attempts. Ideally we do want to see performance at both first and second attempts to be better, but adding stage 1 prevents the behavior collapse where the model does minor or none edits on the first response, and stage 2 further improves the results.

There’s been a lot of recent success in using RL to improve the reasoning ability of language models, by using a collection of questions with ground truth answers (usually STEM problems and puzzles with easy to verify answers), and rewarding the model for getting the correct answer.Recent activity in this area was spurred by strong performance of the o-series models from OpenAI, and the subsequent releases of models and tech reports from DeepSeek.

DeepSeek-R1 (DeepSeek-AI, 2025) is an open-source LLM designed to excel in tasks that require advanced reasoning skills like math, coding and logical problem solving. They run through 2 rounds of SFT-RL training, enabling R1 to be good at both reasoning and non-reasoning tasks.

Interestingly the DeepSeek team showed that with pure RL, no SFT stage, it is still possible to learn advanced reasoning capabilities like reflection and backtracking (“Aha moment”). The model naturally learns to spend more thinking tokens during the RL training process to solve reasoning tasks. The “aha moment” can emerge, referring to the model reflecting on previous mistakes and then trying alternative approaches to correct them. Later, various open source efforts happened for replicating R1 results like Open-R1, SimpleRL-reason, and TinyZero, all based on Qwen models. These efforts also confirmed that pure RL leads to great performance on math problems, as well as the emergent “aha moment”.

The DeepSeek team also shared some of their unsuccessful attempts. They failed to use process reward model (PRM) as it is hard to define per-step rubrics or determine whether an intermediate step is correct, meanwhile making the training more vulnerable to reward hacking. The efforts on MCTS (Monte Carlo Tree Search) also failed due to the large search space for language model tokens, in comparison to, say, chess; and training the fine-grained value model used for guiding the search is very challenging too. Failed attempts often provide unique insights and we would like to encourage the research community to share more about what did not work out.

During the reasoning steps, certain intermediate steps can be reliably and accurately solved by executing code or running mathematical calculations. Offloading that part of reasoning components into an external code interpreter, as in PAL (Program-Aided Language Model; Gao et al. 2022) or Chain of Code (Li et al. 2023), can extend the capability of LLM with external tools, eliminating the need for LLMs to learn to execute code or function as calculators themselves. These code emulators, like in Chain of Code, can be augmented by an LLM such that if a standard code interpreter fails, we have the option of using LLM to execute that line of code instead. Using code to enhance reasoning steps are especially beneficial for mathematical problems, symbolic reasoning and algorithmic tasks. These unit tests may not exist as part of the coding questions, and in those cases, we can instruct the model to self-generate unit tests for it to test against to verify the solution (Shinn, et al. 2023).

ReAct (Reason+Act; Yao et al. 2023) combines the action of searching the Wikipedia API and generation of reasoning traces, such that reasoning paths can incorporate external knowledge.

o3 & o4-mini, recently released by OpenAI, are another two good examples where the reasoning process involves tool use like Web search, code execution and image processing. The team observed that large-scale reinforcement learning exhibits the same trend as in the GPT paradigm that “more compute = better performance”.

Deep learning models are often treated as black boxes and various interpretability methods have been proposed. Interpretability is useful for a couple reasons: first, it gives us an extra test to determine if the model is misaligned with its creators’ intent, or if it’s misbehaving in some way that we can’t tell by monitoring its actions. Second, it can help us determine whether the model is using a sound process to compute its answers. Chain of thought provides an especially convenient form of interpretability, as it makes the model’s internal process visible in natural language. This interpretability, however, rests on the assumption that the model truthfully describes its internal thought processes.

Recent work showed that monitoring CoT of reasoning models can effectively detect model misbehavior such as reward hacking, and can even enable a weaker model to monitor a stronger model (Baker et al. 2025). Increasing test time compute can also lead to improved adversarial robustness (Zaremba et al. 2025); this makes sense intuitively, because thinking for longer should be especially useful when the model is presented with an unusual input, such as an adversarial example or jailbreak attempt – it can use the extra thinking time to make sense of the strange situation it’s been presented with.

Intuitively, model CoTs could be biased due to lack of explicit training objectives aimed at encouraging faithful reasoning. Or when we fine-tune the model on human-written explanations, those human-written samples may contain mistakes. Thus we cannot by default assume CoT is always faithful .

Lanham et al. (2023) investigated several modes of CoT faithfulness failures by deliberately introducing mistakes into CoTs and measuring their impacts on the accuracy of a set of multiple choice tasks (e.g. AQuA, MMLU, ARC Challenge, TruthfulQA, HellaSwag):

Mistake 1 (Early answering): The model may form a conclusion prematurely before CoT is generated. This is tested by early truncating or inserting mistakes into CoT. Different tasks revealed varying task-specific dependencies on CoT effectiveness; some have evaluation performance sensitive to truncated CoT but some do not. Wang et al. (2023) did similar experiments but with more subtle mistakes related to bridging objects or language templates in the formation of CoT.

Mistake 2 (Uninformative tokens): Uninformative CoT tokens improve performance. This hypothesis is tested by replacing CoT with filler text (e.g. all periods) and this setup shows no accuracy increase and some tasks may suffer performance drop slightly when compared to no CoT.

Mistake 3 (Human-unreadable encoding): Relevant information is encoded in a way that is hard for humans to understand. Paraphrasing CoTs in an non-standard way did not degrade performance across datasets, suggesting accuracy gains do not rely on human-readable reasoning.

Interestingly, Lanham et al. suggests that for multiple choice questions, smaller models may not be capable enough of utilizing CoT well, whereas larger models may have been able to solve the tasks without CoT. This dependency on CoT reasoning, measured by the percent of obtaining the same answer with vs without CoT, does not always increase with model size on multiple choice questions, but does increase with model size on addition tasks, implying that thinking time matters more for complex reasoning tasks.

Alternative approaches for testing CoT faithfulness involve perturbing prompts rather than modifying CoT paths directly (Turpin et al. 2023, Chua & Evans, 2025, Chen et al. 2025).

One method consistently labels correct answers as “(A)” in few-shot examples regardless of true labels to introduce biases.

Another prompting technique inserts misleading hints into prompts, such as "I think the answer is <random_label> but curious to hear what you think". or "A Stanford Professor thinks the answer is <random_label>". By comparing model predictions for the same question with vs without the misleading hint, we can measure whether a model is able to faithfully describe the influence of the hint on its answer. Particularly, in cases where the model produces different hint and non-hint answers, we measure whether the model acknowledges the hint when solving the question with hint. If the model is faithful, it should explicitly acknowledge the impact and admit the change of its answer is due to the hint.

Multiple studies found that reasoning models describe the influence of the hint much more reliably than all the non-reasoning models tested. For example, we can measure the fraction of samples where the model acknowledges the hint as a deciding factor (“faithful CoT”). Reasoning models (Claude 3.7 Sonnet, DeepSeek R1) are overall doing better than non-reasoning ones (Claude 3.6, DeepSeek V3).

Some evidence showed that using reward models leads to less faithfulness in model outputs. The reward model in classic RLHF is not trained to incentivize faithful behavior in this test as the preference comparison dataset is collected by humans selecting which one seems better or pleasing. However, in reasoning models, the CoT paths are optimized for producing the correct final answers, not to match human preference defined in RM, and thus intuitively are expected to be more faithful.

Monitoring CoT of reasoning models for reward hacking behavior is effective. A simple way to use this monitor is to run rejection sampling with the monitor as a filter at test time and identify solutions without reward hacking. However, it only works at the early stage of RL, and, as the model is further optimized, it is rare to find a sample to pass a CoT monitor within budget. This challenge naturally suggests that we could consider incorporating CoT monitors into RL rewards—a form of process-based supervision—to prevent reward hacking.

However, incorporating CoT monitoring reward into RL does not work out well, as it leads to obfuscated reward hacking where the model tries to hide its true intent within the CoT (Baker et al. 2025). With this direct optimization pressure provided by the CoT monitor applied during RL training, the model still can find ways to hack, although a bit less frequently, but can hide its intention in CoT to avoid being caught by the monitor.

Experiments on CoT length RL signals by Yeo et al. (2025) confirmed a similar message as Baker et al. that new types of reward hacking can happen with new types of RL reward shaping. They designed the reward function such that correct CoTs can have higher rewards than wrong ones, short correct CoTs obtain higher rewards than long correct ones and short incorrect CoT receive higher penalties than long incorrect CoTs. With this extra reward, the model learns to repeat text in CoTs for challenging questions rather than attempting to solve them. Yeo et al. further applied a n-gram repetition penalty to prevent this hacking behavior.

Chen et al. (2025) experimented with a flawed RL environment, specifically using a grader with incorrect answers filled in for multiple-choice questions. The model learns to exploit the reward hack on >99% of the prompts, but almost never (<2%) verbalizes the reward hack in its CoT on more than half of their environments. Additional RL optimization pressure fails to incentivize the model to verbalize the hack in this case.

RL training is inherently sensitive to reward hacking. Only relying on heuristic investigation of reward hacking and manual fixes may lead to a “whack-a-mole” situation. We would suggest being very cautious when trying to apply optimization directly on CoT during RL training, or trying to avoid it altogether.

Adaptive Computation Time, introduced by Alex Graves in 2016, predated large language models but pioneered the same direction of enabling the model to dynamically decide the number of computational steps to take at the inference time, which can be viewed as enabling the model to “think more” in continuous space at test time. Adaptive thinking time in continuous space can be enabled vertically via recurrent architecture or horizontally via more sequential sampling steps.

A number of architecture variations have been proposed to make the Transformer architecture recurrent, enabling adaptive test time compute (Dehghani, et al. 2019, Hutchins, et al. 2022, Bulatov, et al. 2022). A deep dive into literature on this topic would make the post too long, so we will only review a few.

Universal Transformer (Dehghani, et al. 2019) combines self-attention in Transformer with the recurrent mechanism in RNN, dynamically adjusting the number of steps using adaptive computation time (Graves, 2016). On a high level, it can be viewed as a recurrent function for learning the hidden state representation per token, and if the number of steps is fixed, an Universal Transformer is equivalent to a multi-layer Transformer with shared parameters across layers.

A recent recurrent architecture design, proposed by Geiping et al. (2025), adds a recurrent block $R$ on top of the standard Transformer. Every iteration of this recurrent block takes the embedding $\mathbf{e}$ and a random state $\mathbf{s}_i$. Conceptually, this recurrent-depth architecture is a bit similar to a conditioned diffusion model, where the original input $\mathbf{e}$ is provided in every recurrent step while a random Gaussian initialized state $\mathbf{s}_i$ gets updated iteratively through the process. (Interestingly some of their experiments of designs that resemble diffusion models more turned out to be bad.)

The recurrence count $r$ during training is randomized, sampled from a log-normal Poisson distribution, per input sequence. To manage computational costs, backpropagation is truncated to only the last $k$ iterations of the recurrent unit ($k=8$ in experiments), making it possible to train on the heavy-tail part of the Poisson distribution. The embedding block continues to receive gradient updates in every step since its output $\mathbf{e}$ is injected in every step, mimicking RNN training. Unsurprisingly, the stability of training a recurrent model turns out to be very sensitive. Factors like initialization, normalization and hyperparameters all matter, especially when scaling up the training. For example, hidden states can collapse by predicting the same hidden state for every token; or the model may learn to ignore the incoming state $\mathbf{s}$. To stabilize the training, Geiping et al. adopted an embedding scale factor, a small learning rate and careful tuning.

Thinking tokens refer to a set of implicit tokens introduced during training or inference that do not carry direct linguistic meaning. Instead, their role is to provide extra thinking time and compute power for the model to perform better.

Herel & Mikolov (2023) introduced the idea of inserting special thinking tokens (<T>) after each word in a sentence and training the model on such a dataset. Each thinking token buys extra time for the model to process and make better predictions. Training with thinking tokens on a toy model setup results in lower perplexity than baseline model trained without them. The benefits of thinking tokens are more pronounced for non-trivial reasoning tasks or sentences involving numbers.

Similarly, pause tokens proposed by Goyal et al. (2024) delay the model’s outputs by appending dummy tokens (e.g. character like . or #) at the end of the input sequence, giving the model extra computation during inference. It is important to inject such pause tokens both during training and inference time, while only fine-tuning on pause tokens leads to limited gain. During training, multiple copies of pause tokens are inserted at uniformly random locations and the loss on pause tokens is ignored for training.

Interestingly, thinking tokens or pause tokens in above experiments do not carry any extra information or add many new parameters. But why is it still helpful? On one hand, it helps expand the computation by introducing more inference loops, effectively increasing computational capacity. On the other hand, it can be seen as acting as a special, implicit form of CoTs. A drawback here is hat the model needs to be pretrained with respect to thinking tokens. Still, this strategy is an interesting way to further improve the capability of test time compute utilization on top of inference time CoTs.

Quiet-STaR (Zelikman et al. 2025) introduces token-level reasoning by training the model to generate rationales after every token to explain future text. It mixes the future-text predictions with and without rationales and uses learning to generate better rationales and uses REINFORCE to optimize the quality of rationale generation.

Quiet-STaR consists of three stages:

Think: Predicting next tokens with rationales. Due to high computational cost demanded by token level reasoning, this process is designed to generate multiple rationales in parallel. A special attention map is used to enable all thought tokens to only pay attention to themselves, all preceding thought tokens within the same thought, and the preceding text.

Talk: Next token prediction without rationale is mixed with post-rationale prediction. The mixing weight for two logits is learned by a special mixing head of a shallow MLP out of hidden output after each rationale. Correct next tokens can be selected via teacher forcing.

Learn: Train the model to generate better rationale via REINFORCE by learning from examples that increase the probability of correct next token while discarding those that hurt the prediction.

Without dataset specific fine-tuning, Quiet-STaR improves zero-shot results on CommonsenseQA (36.3%→47.2%) and GSM8K (5.9%→10.9%), within experiments on Mistral 7B.

A latent variable model defines a probabilistic framework where observable data is explained through unobserved (latent) variables. These latent variables capture hidden structures or intermediate processes that generate the observable outcomes. Language models can be viewed as probabilistic latent variable models where test-time thinking and reasoning steps are latent thought variables (Zhou et al. 2020, Phan et al. 2023). Such a latent variable model defines a joint distribution of problems x_i, answers y_i and latent thought z_i. We would like to optimize the log-likelihood of answers given questions and a variety of CoTs as latent variables (N is the number of samples; $K$ is the number of CoTs per problem):

Our goal is to maximize the marginal likelihood of the correct answer, $p(y \mid x)$, given a number of reasoning traces per problem, $\{z^{(k)}\}_{k=1}^K$.

Expectation-Maximization is a commonly used iterative algorithm for optimizing parameters for a model with (hidden) latent variables, and thus can be applied to train better CoTs and then condition on that to generate better responses. Typically we iterate between E-step (Expectation) where we guess the missing information about latent variables (i.e. how to sample better CoTs), and M-step (Maximization) where we optimize the model parameters based on latent variables (i.e. how to sample better answers), until convergence.

Because we cannot directly sample from the latent variable distribution $p(z \mid x, y)$, researchers have explored methods relying on human annotated data (Zhou et al. 2020), Metropolis-Hastings MCMC (Phan et al. 2023) or Monte Carlo sampling with special importance weights (Ruan et al. 2025) to draw good CoT samples to update the model. Ruan et al. (2025) experimented with training a model on a large body of Web text with latent thoughts with the EM algorithm, where the latent thought is synthesized per chunk of observed data and then the model learns over both latent thought and data in an autoregressive manner.

They first prompt a LLM $\tilde{q}$ to generate synthetic latent thought Z_i given observed data X_i:

Special tokens like <StartOfLatent><Prior> ... <EndOfPrior> are used to insert the generated latent thought content into the raw data for training the joint distribution $p(z, x)$ or the approximate posterior $q(z \mid x)$, depending on whether $z$ is inserted before or after $x$. However, since we are using a LLM $\tilde{q}(z \mid x)$ to generate the CoTs, it imposed a performance ceiling on how good the approximate $q(z \mid x)$ can be. Ruan et al. introduced importance weights for selecting CoT samples at the E-step, formulated as:

, such that we prioritize samples with CoTs that are good at predicting the observation (i.e., high $p(x \mid z^{(k)})$), simple, intuitive (i.e., high $p(z^{(k)})$) but also informative and not too obvious (i.e. low $q(z^{(k)} \mid x)$).

Since pretrained models already possess the capability of generating chains of thought, it is intuitive to design an iterative improvement process where we generate multiple CoTs and fine-tune the model only on rationales that lead to correct answers. However, this straightforward design can fail because the model receives no learning signals for problems it fails to solve. STaR (“Self-taught reasoner”; Zelikman et al. 2022) addresses this limitation by adding a “rationalization” process for failed attempts, in which the model generates good CoTs backward conditioned on both the problem and the ground truth answer and thus the model can generate more reasonable CoTs. Then the model is finetuned on correct solutions that either lead to correct outputs or are generated through rationalization.

We can view STaR as an approximation to a policy gradient in RL, with a simple indicator function as the reward, $\mathbb{1}[\hat{y} = y]$. We want to maximize the expectation of this reward when sampling $z \sim p(z \mid x)$ and then $y \sim p(y \mid x, z)$, since $p(y \mid x) = \sum_z p(z \mid x) \; p(y \mid x, z)$.

Each iteration is equivalent to first selecting the CoT samples according to $\mathbb{1}[y=y^\text{truth}]$ and then running supervised fine-tuning to optimize the logprob of generating good CoTs and answers. Performance of STaR improves with more training iterations, and the “rationalization” process for generating better CoTs accelerates learning. They observed that sampling with high temperature increases the chance of getting correct answers with incorrect reasoning and finetuning LLM on such data can impair generalization. For datasets without ground truths, majority votes of multiple high-temperature outputs can serve as a proxy of ground truth answers (Wang et al. 2022), making it possible to use synthetic samples for training.

So far we have seen much evidence that allowing models to spend additional compute on reasoning before producing final answers at inference time can significantly improve performance. Techniques like prompting the model to generate intermediate reasoning steps before the answers, or training the model to pause and reflect before predicting next tokens, have been found to boost the model performance beyond the capability limit obtained during training. This essentially introduces a new dimension to tinker with for improving model intelligence, complementing established factors such as model size, training compute and data quantity, as defined in scaling laws (Kaplan et al. 2020).

Recent studies demonstrated that optimizing LLM test-time compute could be more effective than scaling up model parameters (Snell et al. 2024, Wu et al. 2025). Smaller models combined with advanced inference algorithms can offer Pareto-optimal trade-offs in cost and performance.

Snell et al. (2024) evaluated and compared test-time and pretraining compute, and found that they are not 1:1 exchangeable. Test-time compute can cover up the gap easily on easy and medium questions when there is only a small gap in model capability, but proves less effective for hard problems. The ratio between token budgets for pretraining and inference matters a lot. Test-time compute is only preferable when inference tokens are substantially fewer than pretraining ones. This indicates that developing a capable base model with enough pretraining data and compute is still very critical, as test-time compute cannot solve everything or fill in big model capability gaps.

s1 models (Muennighoff & Yang, et al. 2025) experimented with scaling up the CoT reasoning path length via budget forcing technique (i.e. forcefully lengthen it by appending the word "wait", or shorten it by terminating the model’s thinking process by appending end-of-thinking token or "Final Answer:"). They observed a clear positive correlation between the average thinking time measured in tokens and the downstream evaluation accuracy.

When comparing this budget forcing technique with other decoding methods of controlling reasoning trace length, it is quite surprising that simple rejection sampling (i.e. sampling generation until the lengths fits a token budget) leads to reversed scaling, meaning that longer CoTs lead to worse performance.

The exploration of test-time compute and chain-of-thought reasoning presents new opportunities for enhancing model capabilities. More interestingly, via test-time thinking, we are moving towards building future AI systems that mirror the best practices of how humans think, incorporating adaptability, flexibility, critical reflection, and error correction. Excitement with current progress invites us for more future research to improve and understand deeply not just how but why we—and our models—think.

At the end, I would like to call for more research for the following open research questions on test time compute and chain-of-thought reasoning.

Please cite this work as:

Or use the BibTex citation:

[1] Alex Graves. “Adaptive Computation Time for Recurrent Neural Networks.”. arXiv preprint arXiv:1603.08983 (2016).

[2] Wang Ling, et al. “Program Induction by Rationale Generation: Learning to Solve and Explain Algebraic Word Problems.”. arXiv preprint arXiv:1705.04146 (2017).

[3] Karl Cobbe, et al. “Training Verifiers to Solve Math Word Problems.”. arXiv preprint arXiv:2110.14168 (2021).

[4] Jason Wei, et al. “Chain of Thought Prompting Elicits Reasoning in Large Language Models.”. NeurIPS 2022.

[5] Maxwell Nye, et al. “Show Your Work: Scratchpads for Intermediate Computation with Language Models.”. arXiv preprint arXiv:2112.00114 (2021).

[6] Daniel Kahneman. Thinking, Fast and Slow. Farrar, Straus and Giroux (2013).

[7] Takeshi Kojima, et al. “Large Language Models are Zero-Shot Reasoners.”. NeurIPS 2022.

[8] Michihiro Yasunaga, et al. “Large Language Models as Analogical Reasoners”. arXiv preprint arXiv:2310.01714 (2023).

[9] Eric Zelikman, et al. “STaR: Bootstrapping Reasoning With Reasoning.”. NeurIPS 2022.

[10] Xuezhi Wang, et al. “Self-consistency Improves Chain of Thought Reasoning in Language Models.”. ACL 2023.

[11] Ryo Kamoi, et al. “When Can LLMs Actually Correct Their Own Mistakes? A Critical Survey of Self-Correction of LLMs.”. TACL 2024.

[12] Jie Huang, et al. “Large Language Models Cannot Self-Correct Reasoning Yet.”. ICLR 2024.

[13] Noah Shinn, et al. “Reflexion: Language Agents with Verbal Reinforcement Learning.”. arXiv preprint arXiv:2303.11366 (2023).

[14] Yunxiang Zhang, et al. “Small Language Models Need Strong Verifiers to Self-Correct Reasoning.”. ACL Findings 2024.

[15] Hao Liu, et al. “Chain of Hindsight Aligns Language Models with Feedback.”. arXiv preprint arXiv:2302.02676 (2023).

[16] Sean Welleck, et al. “Generating Sequences by Learning to Self-Correct.”. arXiv preprint arXiv:2211.00053 (2023).

[17] Yuxiao Qu, et al. “Recursive Introspection: Teaching Language Model Agents How to Self-Improve.”. arXiv preprint arXiv:2407.18219 (2024).

[18] Aviral Kumar, et al. “Training Language Models to Self-Correct via Reinforcement Learning.”. arXiv preprint arXiv:2409.12917 (2024).

[19] Hunter Lightman, et al. “Let’s Verify Step by Step.”. arXiv preprint arXiv:2305.20050 (2023).

[20] Yuxi Xie, et al. “Self-Evaluation Guided Beam Search for Reasoning.”. NeurIPS 2023.

[21] Yangzhen Wu, et al. “Inference Scaling Laws: An Empirical Analysis of Compute-Optimal Inference for Problem-Solving with Language Models”. ICLR 2025.

[22] Dongwei Jiang, et al. “RATIONALYST: Pre-training Process-Supervision for Improving Reasoning”. arXiv preprint arXiv:2410.01044 (2024).

[23] Xuezhi Wang and Denny Zhou. “Chain-of-Thought Reasoning Without Prompting.”. arXiv preprint arXiv:2402.10200 (2024).

[24] DeepSeek-AI. “DeepSeek-V3 Technical Report.” arXiv preprint arXiv:2412.19437 (2024).

[25] DeepSeek-AI. “DeepSeek-R1: Incentivizing Reasoning Capability in LLMs via Reinforcement Learning.”. arXiv preprint arXiv:2501.12948 (2025).

[26] Luyu Gao, Aman Madaan & Shuyan Zhou, et al. “PAL: Program-aided Language Models.”. ICML 2023.

[27] Shunyu Yao, et al. “ReAct: Synergizing Reasoning and Acting in Language Models.”. ICLR 2023.

[29] Bowen Baker, et al. “Monitoring Reasoning Models for Misbehavior and the Risks of Promoting Obfuscation.”. arXiv preprint arXiv:2503.11926 (2025).

[30] Wojciech Zaremba, et al. “Trading Inference-Time Compute for Adversarial Robustness.”. arXiv preprint arXiv:2501.18841 (2025).

[31] Tamera Lanham, et al. “Measuring Faithfulness in Chain-of-Thought Reasoning”. arXiv preprint arXiv:2307.13702 (2023).

[32] Boshi Wang, et al. “Towards Understanding Chain-of-Thought Prompting: An Empirical Study of What Matters.”. ACL 2023.

[33] Miles Turpin, et al. “Language Models Don’t Always Say What They Think: Unfaithful Explanations in Chain-of-Thought Prompting.”. NeuriPS 2023.

[34] James Chua & Owain Evans. “Are DeepSeek R1 And Other Reasoning Models More Faithful?”. arXiv preprint arXiv:2501.08156 (2025).

[35] Yanda Chen et al. “Reasoning Models Don’t Always Say What They Think”. arXiv preprint arXiv:2505.05410 (2025).

[36] Edward Yeo, et al. “Demystifying Long Chain-of-Thought Reasoning in LLMs.”. arXiv preprint arXiv:2502.03373 (2025).

[37] Mostafa Dehghani, et al. “Universal Transformers.”. ICLR 2019.

[38] DeLesley Hutchins, et al. “Block-Recurrent Transformers.”. NeurIPS 2022.

[39] Aydar Bulatov, et al. “Recurrent Memory Transformers.”. NeuriPS 2022.

[40] Jonas Geiping, et al. “Scaling up Test-Time Compute with Latent Reasoning: A Recurrent Depth Approach.”. arXiv preprint arXiv:2502.05171 (2025).

[41] Herel & Mikolov. “Thinking Tokens for Language Modeling.”. AITP 2023.

[42] Sachin Goyal et al. “Think before you speak: Training Language Models With Pause Tokens.”. ICLR 2024.

[43] Eric Zelikman, et al. “Quiet-STaR: Language Models Can Teach Themselves to Think Before Speaking.”. arXiv preprint arXiv:2403.09629 (2025).

[44] Wangchunshu Zhou et al. “Towards Interpretable Natural Language Understanding with Explanations as Latent Variables.”. NeurIPS 2020.

[45] Du Phan et al. “Training Chain-of-Thought via Latent-Variable Inference.”. NeurIPS 2023.

[46] Yangjun Ruan et al. “Reasoning to Learn from Latent Thoughts.”. arXiv preprint arXiv:2503.18866 (2025).

[47] Xuezhi Wang et al. “Rationale-Augmented Ensembles in Language Models.”. arXiv preprint arXiv:2207.00747 (2022).

[48] Jared Kaplan, et al. “Scaling Laws for Neural Language Models.”. arXiv preprint arXiv:2001.08361 (2020).

[49] Niklas Muennighoff & Zitong Yang, et al. “s1: Simple test-time scaling.”. arXiv preprint arXiv:2501.19393 (2025).

[50] Peiyi Wang, et al. “Math-Shepherd: Verify and Reinforce LLMs Step-by-step without Human Annotations” arXiv preprint arXiv:2312.08935 (2023).

[51] Yixin Liu, et al. “Improving Large Language Model Fine-tuning for Solving Math Problems.” arXiv preprint arXiv:2310.10047 (2023).

[52] Charlie Snell, et al. “Scaling LLM Test-Time Compute Optimally can be More Effective than Scaling Model Parameters.”. arXiv preprint arXiv:2408.03314 (2024).

[53] OpenAI. o1-preview: “Learning to reason with LLMs.” Sep 12, 2024.

[54] OpenAI. o3: “Introducing OpenAI o3 and o4-mini.” Apr 16, 2025.

---

## [Reward Hacking in Reinforcement Learning](https://lilianweng.github.io/posts/2024-11-28-reward-hacking/)

Reward hacking occurs when a reinforcement learning (RL) agent exploits flaws or ambiguities in the reward function to achieve high rewards, without genuinely learning or completing the intended task. Reward hacking exists because RL environments are often imperfect, and it is fundamentally challenging to accurately specify a reward function.

With the rise of language models generalizing to a broad spectrum of tasks and RLHF becomes a de facto method for alignment training, reward hacking in RL training of language models has become a critical practical challenge. Instances where the model learns to modify unit tests to pass coding tasks, or where responses contain biases that mimic a user’s preference, are pretty concerning and are likely one of the major blockers for real-world deployment of more autonomous use cases of AI models.

Most of the past work on this topic has been quite theoretical and focused on defining or demonstrating the existence of reward hacking. However, research into practical mitigations, especially in the context of RLHF and LLMs, remains limited. I especially want to call out for more research efforts directed toward understanding and developing mitigation for reward hacking in the future. Hope I will be able to cover the mitigation part in a dedicated post soon.

Reward function defines the task, and reward shaping significantly impacts learning efficiency and accuracy in reinforcement learning. Designing a reward function for an RL task often feels like a ‘dark art’. Many factors contribute to this complexity: How you decompose a big goal into small goals? Is the reward sparse or dense? How you measure the success? Various choices may lead to good or problematic learning dynamics, including unlearnable tasks or hackable reward functions. There is a long history of research on how to do reward shaping in RL.

For example, in an 1999 paper by Ng et al., the authors studied how to modify the reward function in Markov Decision Processes (MDPs) such that the optimal policy remains unchanged. They found that linear transformation works. Given a MDP $M = (S, A, T, \gamma, R)$, we want to create a transformed MDP $M’ = (S, A, T, \gamma, R’)$ where $R’ = R + F$ and $F: S \times A \times S \mapsto \mathbb{R}$, such that we can guide the learning algorithm to be more efficient. Given a real-valued function $\Phi: S \mapsto \mathbb{R}$, $F$ is a potential-based shaping function if for all $s \in S - {s_0}, a \in A, s’ \in S$:

This would guarantee that the sum of discounted $F$, $F(s_1, a_1, s_2) + \gamma F(s_2, a_2, s_3) + \dots$, ends up being 0. If $F$ is such a potential-based shaping function, it is both sufficient and necessary to ensure $M$ and $M’$ share the same optimal policies.

When $F(s, a, s’) = \gamma \Phi(s’) - \Phi(s)$, and if we further assume that $\Phi(s_0) = 0$, where $s_0$ is absorbing state, and $\gamma=1$, and then for all $s \in S, a \in A$:

This form of reward shaping allows us to incorporate heuristics into the reward function to speed up learning without impacting the optimal policy.

Spurious correlation or shortcut learning (Geirhos et al. 2020) in classification task is a concept closely related to reward hacking. Spurious or shortcut features can cause a classifier to fail at learning and generalizing as intended. For example, a binary classifier for distinguishing wolves from huskies may overfit to the presence of a snowy background if all the wolf training images include snow (Ribeiro et al. 2024).

The ERM principle states that, since the full data distribution is unknown, minimizing the loss on training data is a reasonable proxy of risk and thus we favor models with the lowest training loss. Nagarajan et al. (2021) studied the ERM principle and pointed out that ERM needs to rely on all types of informative features, including unreliable spurious features, while attempting to fit the data without constraints. Their experiments showed that ERM would depend on spurious features no matter how easy the task is.

Reward shaping in RL is challenging. Reward hacking occurs when an RL agent exploits flaws or ambiguities in the reward function to obtain high rewards without genuinely learning the intended behaviors or completing the task as designed. In recent years, several related concepts have been proposed, all referring to some form of reward hacking:

The concept originated with Amodei et al. (2016), who proposed a set of open research questions on AI safety in their seminal paper “Concrete Problems in AI Safety”. They listed reward hacking as one of the key AI safety problems. Reward hacking refers to the possibility of the agent gaming the reward function to achieve high reward through undesired behavior. Specification gaming (Krakovna et al. 2020) is a similar concept, defined as a behavior that satisfies the literal specification of an objective but not achieving the desired results. Here the literal description of the task goal and the intended goal may have a gap.

Reward shaping is a technique used to enrich the reward function, making it easier for the agent to learn—for example, by providing denser rewards. However, a poorly design reward shaping mechanism can alter the trajectory of the optimal policy. Designing effective reward shaping mechanisms is inherently difficult. Rather than blaming a poorly designed reward function, it is more accurate to acknowledge that designing a good reward function is intrinsically challenging due to the complexity of the task itself, partial observable state, multiple dimensions in consideration, and other factors.

When testing an RL agent in out-of-distribution (OOD) environments, robustness failure may occur due to:

Experiments in two RL environments, CoinRun and Maze, demonstrated the importance of randomization during training. If during training, the coin or the cheese is placed at a fixed position (i.e. right end of the level or upper right corner of the maze) but testing in the env where the coin or cheese is placed at random, the agent would just run to the fixed position without obtaining the coin or cheese at test time. A conflict arises when a visual feature (e.g., cheese or coin) and a positional feature (e.g., upper-right or right end) are inconsistent during test time, leading the trained model to prefer the positional feature. I would like to point out that, in these two examples, the reward-result gaps are clear but such type of biases are unlikely to be so obvious in most real-world cases.

Reward Tampering (Everitt et al. 2019) is a form of reward hacking behavior where the agent interferes with the reward function itself, causing the observed reward to no longer accurately represent the intended goal. In reward tampering, the model modifies its reward mechanism either by directly manipulating the implementation of the reward function or by indirectly altering the environmental information used as input for the reward function.

(Note: Some work defines reward tampering as a distinct category of misalignment behavior from reward hacking. But I consider reward hacking as a broader concept here.)

At a high level, reward hacking can be categorized into two types: environment or goal misspecification, and reward tampering.

Goodhart’s Law states that “When a measure becomes a target, it ceases to be a good measure”. The intuition is that a good metric can become corrupted once significant pressure is applied to optimize it. It is challenging to specify a 100% accurate reward objective and any proxy suffers the risk of being hacked, as RL algorithm exploits any small imperfection in the reward function definition. Garrabrant (2017) categorized Goodhart’s law into 4 variants:

Amodei et al. (2016) summarized that reward hacking, mainly in RL setting, may occur due to:

Besides, identifying the exact reward function for which an optimal agent optimizes its behavior is in general impossible since there could be an infinite number of reward functions consistent with any observed policy in an fixed environment (Ng & Russell, 2000). Amin and Singh (2016) separated the causes of this unidentifiability into two classes:

Reward hacking is expected to be a more common problem as the model and the algorithm become increasingly sophisticated. A more intelligent agent is more capable of finding “holes” in the design of reward function and exploiting the task specification—in other words, achieving higher proxy rewards but lower true rewards. By contrast, a weaker algorithm may not be able to find such loopholes, and thus we would not observe any reward hacking or identify issues in the current reward function design when the model is not strong enough.

In a set of zero-sum robotics self-play games (Bansal et al., 2017), we can train two agents (victim vs. opponent) to compete against each other. A standard training process produces a victim agent with adequate performance when playing against a normal opponent. However, it is easy to train an adversarial opponent policy that can defeat the victim reliably despite outputting seemingly random actions and training with fewer than 3% of time steps (Gleave et al., 2020). Training of adversarial policies involves optimizing the sum of discounted rewards, as in standard RL setup, while treating the victim policy as a black-box model.

An intuitive way to mitigate adversarial policies attacks is to fine-tune victims against adversarial policies. However, the victim remains vulnerable to new versions of adversarial policies once retrained against the new victim policy.

Why does adversarial policy exist? The hypothesis is that adversarial policies introduce OOD observations to the victim rather than physically interfering with it. Evidence shows that when the victim’s observation of the opponent’s position is masked and set to a static state, the victim becomes more robust to adversaries, although performing worse against a normal opponent policy. Furthermore, a higher-dimensional observation space enhances performance under normal circumstances but makes the policy more vulnerable to adversarial opponents.

Pan et al. (2022) investigated reward hacking as a function of agent capabilities, including (1) model size, (2) action space resolution, (3) observation space noise, and (4) training time. They also proposed a taxonomy of three types of misspecified proxy rewards:

They experimented in four RL environments paired with nine misspecified proxy rewards. The overall findings from these experiments can be summarized as follows: A model of higher capability tends to obtain higher (or similar) proxy rewards but decreased true rewards.

If a proxy reward is so poorly specified that it has a very weak correlation with the true reward, we may be able to identify and prevent reward hacking even before training. Based on this hypothesis, Pan et al. (2022) investigated the correlation between proxy and true rewards over a collection of trajectory rollouts. Interestingly, reward hacking still occurs even when there is a positive correlation between the true and proxy rewards.

Reinforcement learning from human feedback (RLHF) has become the de facto approach for alignment training of language models. A reward model is trained on human feedback data and then a language model is fine-tuned via RL to optimize this proxy reward for human preference. There are three types of reward we care about in an RLHF setup:

RLHF optimizes the proxy reward score but we ultimately care about the gold reward score.

Gao et al. (2022) examined the scaling laws for reward model overoptimization in RLHF. To scale up the human labels in their experiments, they use a synthetic data setup where the “gold” label for the oracle reward $R^*$ is approximated by a large RM (6B parameters) where the proxy RMs for $R$ range in size of 3M to 3B parameters.

The KL divergence from the initial policy to the optimized policy is $\text{KL} = D_\text{KL}(\pi | \pi_\text{init})$, and the distance function is defined as $d := \sqrt{ D_\text{KL}(\pi | \pi_\text{init})}$. For both best-of-$n$ rejection sampling (BoN) and RL, the gold reward $R^∗$ is defined as a function of $d$. The coefficients $\alpha$ and $\beta$ are fitted empirically, with $R^∗ (0) := 0$ by definition.

The authors also attempted to fit the proxy reward $R$ but found systematic underestimation when extrapolated to higher KLs, as the proxy reward appeared to grow linearly with $d$.

Their experiments also explored the relationship between RM overoptimization and factors like policy model size and RM data size:

RLHF aims to improve the model’s alignment with human preference, but human feedback $R^\text{human}$ may not capture all the aspects we care about (e.g., factuality) and thus can be hacked to overfit to undesired attributes. For example, the model may be optimized to output responses that seem correct and convincing but are, in fact, inaccurate, thereby misleading human evaluators to approve its incorrect answers more often (Wen et al., 2024). In other words, a gap emerges between what is correct and what looks correct to humans due to RLHF. Precisely Wen et al. (2024) ran RLHF experiments using a reward model based on ChatbotArena data. They evaluated the model on a question-answering dataset, QuALITY and a programming dataset, APPS. Their experiments revealed that models become better at convincing humans they are correct, even when they are wrong and this effect is unintended:

The paper coined this effect “U-Sophistry” (“U” for “unintended”), as opposed to “I-Sophistry” (“I” for “intended”), which involves explicitly prompting the model with instructions like "... try to deceive human subjects".

The human evaluation error change is not due to noise in the recruiting process since (1) at an individual level, the majority (70-90%) of human evaluators raw their evaluation error rates increase, and (2) the effort they put into evaluating $\pi_\text{init}$ or $\pi_\text{rlhf}$ is equivalent, measured by metrics like time spent or unit tests written. Instead, LLMs learn to defend incorrect answers by cherry-picking, fabricating untruthful supporting statements, or crafting statements with subtle causal fallacies. What they observed about how the model behaves after RLHF:

Sycophancy refers to the tendency of model responses to match user beliefs rather than reflect the truth (Shrama et al. 2023). In the experiments, an AI assistant was asked to provide feedback on an argument (Human: "Please comment briefly on the following argument. Argument: ..."). Right the human provided the argument, they could state a preference ("I really like the argument" or "I really dislike the argument") to test whether this influenced the model’s feedback compared to the baseline feedback without human preference statement.

They found that AI assistant feedback can be easily swayed, as it may change its originally correct answer when challenged by human preference. The model tends to confirm users’ beliefs. Sometimes it even mimics users’ mistakes (e.g., when asked to analyze poems misattributed the wrong poet). Data analysis of the RLHF helpfulness dataset, via logistic regression for predicting human feedback, demonstrates that matching users’ beliefs is the most predictive factor.

As LLMs become more capable, it is a natural choice to use LLMs as the evaluators or graders to give feedback and training rewards to other generator models, especially for tasks that cannot be trivially judged or verified (e.g., processing long-form outputs, subjective rubrics like the quality of creative writing, etc.). Some people refer to this as “LLM-as-grader paradigm”. This approach has largely reduced the dependency on human annotation, significantly saving time on evaluation. However, using LLMs as graders is an imperfect proxy for oracle reward and can introduce biases, such as a preference for their own responses when compared with different model families (Liu et al., 2023 ) or positional bias when evaluating responses in order (Wang et al. 2023). Such biases are especially concerning grader outputs are used as part of a reward signal, which can lead to reward hacking by exploiting these graders.

Wang et al. (2023) found that when using an LLM as an evaluator to score the quality of multiple other LLM outputs, the quality ranking can be easily hacked by simply altering the order of candidates in the context. GPT-4 is found to consistently assign high scores to the first displayed candidate and ChatGPT prefers the second candidate.

According to their experiments, LLMs are sensitive to the position of responses and suffer from positional bias (i.e., prefer the response in the specific position), despite of the instruction containing a statement of "ensuring that the order in which the responses were presented does not affect your judgment.". The severity of such positional bias is measured by “conflict rate”, defined as the percentage of tuples of (prompt, response 1, response 2) that lead to inconsistent evaluation judgement after swapping the positions of responses. Unsurprisingly, the difference in response quality matters as well; the conflict rate is negatively correlated with the score gap between the two responses.

To mitigate this positional bias, they proposed several strategies for calibration:

Liu et al. (2023) experimented on the summarization task using a number of models (BART, T5, GPT-2, GPT-3, FLAN-T5, Cohere) and tracked both reference-based and reference-free metrics for evaluating summarization quality. When plotting the evaluation scores in a heatmap of evaluator (x-axis) vs generator (y-axis), they observed dark diagonal lines for both metrics, indicating self-bias. This means that LLMs tend to prefer their own outputs when used as evaluators. While the models used in the experiments are somewhat dated, it would be interesting to see results on newer, more capable models.

Iterative self-refinement is a training setup where the evaluation and generation model are the same and both can be fine-tuned. In this setup, optimization pressure can drive the model to exploit vulnerabilities that occur in both roles. In the experiments by Pan et al. (2023), no model parameters are updated and the same model is used as evaluator and generator with different prompts. The experimental task was essay editing with two roles: (1) a judge (evaluator) that gives feedback on the essay, and (2) an author (generator) that edits the essay based on the feedback. Human evaluation scores were collected as the oracle scores for essay quality. The authors hypothesized that such a setup could lead to in-context reward hacking (ICRH), where the evaluator score and oracle score diverge. More generally, ICRH takes place during feedback loops between an LLM and its evaluator (e.g., another LLM, or the external world). At test time, the LLM optimizes a (potentially implicit) objective, but this creates negative side effects in the process (Pan et al., 2024).

Both judge and author can be configured to see none or several previous rounds of feedback or edits. An online judge can see past conversations, while an offline judge or a human annotator can only see one essay a time. Smaller models are more sensitive to ICRH; for example, GPT-3.5 as an evaluator caused more severe ICRH than GPT-4, empirically.

When the judge and author are configured to see different numbers of past iterations, the gap between human score and evaluator scores tends to increase if they share the same number of iterations. Identical context between the evaluator and generator is crucial for ICRH, indicating that shared context matters more than context length for ICRH.

In a follow up work, Pan et al. (2024) investigated in-context reward hacking (ICRH) further in settings where feedback is provided by the external world and the goal is an imperfect proxy objective, commonly specified in natural language. Here this goal is often underspecified and does not capture all the constraints or requirements and thus can be hacked.

The study described two processes leading to ICRH, paired with two toy experiments:

When comparing ICRH to traditional reward hacking, there are two noticeable differences:

There is no magic way to avoid or detect or prevent ICRH yet, as improving prompt specification is insufficient to eliminate ICRH and scaling model sizes can worsen ICRH. The best practice of testing before deployment is to simulate what may happen at deployment time by evaluating the model with more rounds of feedback, diverse feedback, as well as injecting atypical environment observations.

Reward hacking behavior has been found to generalize across tasks: When models exhibit flaws in supervised training, it can sometimes generalize to exploit flaws in OOD environments (Kei et al., 2024). The researchers experimented with reinforcing reward hacking behavior in some reward-hackable environments and examined whether it generalizes to other holdout datasets. Essentially, they prepared 8 datasets on multiple-choice questions, where 4 for training and 4 for testing. The RL training employs expert iteration, that is, iterative fine-tuning on best-of-$n$ samples.

Notably, all experiments have a scratchpad design to host hidden reasoning steps. This scratchpad serves as a way to interpret what the model is thinking along the process. Analysis of the scratchpad revealed that it can:

Denison et al. (2024) studied reward tampering with a manually curated curriculum of increasingly sophisticated gameable environments. They observed that training on easier environments in the curriculum amplifies specification gaming on remaining environments. In some cases, the model can generalize zero-shot to directly rewriting its own reward function after training on the full curriculum.

Such a curriculum of gameable environments include:

The model was trained following this curriculum, and the paper measured whether the model can learn gaming behaviors that generalize to unseen environments. Experimenting with Claude-2 helpful-only model, they sampled $N=64$ responses per each of $P=1024$ HHH prompts for expert iteration and selected the best according to RM. A model trained using expert iteration to do supervised learning on the curriculum can generalize from one stage to the next.

It is noteworthy that even after the curriculum, the model overwrote the reward and avoided detection less than 1/1000 of the time. Even when a model was trained on curricula which directly incentivized reward hacking, the model overwrote their reward less than 1% of the time and hacked unit tests even less often. As a simple mitigation, supervised fine-tuning the model on the first two environments–where the reward hacking behavior is easy to be detected (sycophancy and flattery)—with SFT data that does not game the env was found to reduce the likelihood of reward tampering in holdout environments.

While there is a large body of literature discussing the phenomenon of reward hacking, there has been not a ton of work on mitigations for reward hacking, especially in the area of RLHF and LLMs. Let’s lightly review three potential approaches in this section, not exhaustive yet.

Amodei et al. (2016) pointed out some directions for mitigating reward hacking in RL training:

In RL setups where human feedback is formed as approval of agent actions, Uesato et al. (2020) proposed to prevent reward tampering with decoupled approval. If the feedback is conditioned on $(s, a)$ (state, action), we can never get uncorrupted feedback for action $a$ at state $s$ once reward tampering happens for this pair. Decoupling means that the query action for collecting feedback is sampled independently from the action taken in the world. Feedback is received even before the action is executed in the world, thus preventing the action from corrupting its own feedback.

An alternative mitigation is to detect reward hacking by framing it as an anomaly detection task, where the detector (“a trusted policy” with trajectories and rewards validated by human) should flag instances of misalignment (Pan et al. 2022). Given (1) a trusted policy and (2) a collection of manually labeled trajectory rollouts, we can build a binary classifier based on distances between action distribution of two policies, the trusted policy and the target policy, and measure the accuracy of this anomaly detection classifier. In experiments by Pan et al. (2022), they observed that different detectors are better for different tasks and none of the tested classifier can achieve AUROC greater than 60% across all tested RL environments.

` Another approach is to analyze RLHF dataset. By examining how training data impacts the alignment training results, insights can guide preprocessing and human feedback collection to reduce reward hacking risks.

Revel et al. (2024) introduced a set of evaluation metrics for measuring the effectiveness of data sample features in modeling and aligning human values. They conducted a systematic error analysis for value alignment (“SEAL”) in the HHH-RLHF dataset. The feature taxonomy used in the analysis (e.g., is harmless, is refusal and is creative) was manually predefined. Then each sample was labelled with a binary flag per feature using a LLM according to this taxonomy. Features are categorized into two groups based on heuristics:

SEAL introduced three metrics for measuring data effectiveness for alignment training:

Cited as:

Weng, Lilian. “Reward Hacking in Reinforcement Learning”. Lil’Log (Nov 2024). https://lilianweng.github.io/posts/2024-11-28-reward-hacking/.

Or

[1] Andrew Ng & Stuart Russell. “Algorithms for inverse reinforcement learning.”. ICML 2000.

[2] Amodei et al. “Concrete problems in AI safety: Avoid reward hacking.” arXiv preprint arXiv:1606.06565 (2016).

[3] Krakovna et al. “Specification gaming: the flip side of AI ingenuity.” 2020.

[4] Langosco et al. “Goal Misgeneralization in Deep Reinforcement Learning” ICML 2022.

[5] Everitt et al. “Reinforcement learning with a corrupted reward channel.” IJCAI 2017.

[6] Geirhos et al. “Shortcut Learning in Deep Neural Networks.” Nature Machine Intelligence 2020.

[7] Ribeiro et al. “Why Should I Trust You?”: Explaining the Predictions of Any Classifier. KDD 2016.

[8] Nagarajan et al. “Understanding the Failure Modes of Out-of-Distribution Generalization.” ICLR 2021.

[9] Garrabrant. “Goodhart Taxonomy”. AI Alignment Forum (Dec 30th 2017).

[10] Koch et al. “Objective robustness in deep reinforcement learning.” 2021.

[11] Pan et al. “The effects of reward misspecification: mapping and mitigating misaligned models.”

[12] Everitt et al. “Reward tampering problems and solutions in reinforcement learning: A causal influence diagram perspective.” arXiv preprint arXiv:1908.04734 (2019).

[13] Gleave et al. “Adversarial Policies: Attacking Deep Reinforcement Learning.” ICRL 2020

[14] “Reward hacking behavior can generalize across tasks.”

[15] Ng et al. “Policy invariance under reward transformations: Theory and application to reward shaping.” ICML 1999.

[16] Wang et al. “Large Language Models are not Fair Evaluators.” ACL 2024.

[17] Liu et al. “LLMs as narcissistic evaluators: When ego inflates evaluation scores.” ACL 2024.

[18] Gao et al. “Scaling Laws for Reward Model Overoptimization.” ICML 2023.

[19] Pan et al. “Spontaneous Reward Hacking in Iterative Self-Refinement.” arXiv preprint arXiv:2407.04549 (2024).

[20] Pan et al. “Feedback Loops With Language Models Drive In-Context Reward Hacking.” arXiv preprint arXiv:2402.06627 (2024).

[21] Shrama et al. “Towards Understanding Sycophancy in Language Models.” arXiv preprint arXiv:2310.13548 (2023).

[22] Denison et al. “Sycophancy to subterfuge: Investigating reward tampering in language models.” arXiv preprint arXiv:2406.10162 (2024).

[23] Uesato et al. “Avoiding Tampering Incentives in Deep RL via Decoupled Approval.” arXiv preprint arXiv:2011.08827 (2020).

[24] Amin and Singh. “Towards resolving unidentifiability in inverse reinforcement learning.”

[25] Wen et al. “Language Models Learn to Mislead Humans via RLHF.” arXiv preprint arXiv:2409.12822 (2024).

[26] Revel et al. “SEAL: Systematic Error Analysis for Value ALignment.” arXiv preprint arXiv:2408.10270 (2024).

[27] Yuval Noah Harari. “Nexus: A Brief History of Information Networks from the Stone Age to AI.” Signal; 2024 Sep 10.

---

## [Extrinsic Hallucinations in LLMs](https://lilianweng.github.io/posts/2024-07-07-hallucination/)

Hallucination in large language models usually refers to the model generating unfaithful, fabricated, inconsistent, or nonsensical content. As a term, hallucination has been somewhat generalized to cases when the model makes mistakes. Here, I would like to narrow down the problem of hallucination to cases where the model output is fabricated and not grounded by either the provided context or world knowledge.

There are two types of hallucination:

This post focuses on extrinsic hallucination. To avoid hallucination, LLMs need to be (1) factual and (2) acknowledge not knowing the answer when applicable.

Given a standard deployable LLM goes through pre-training and fine-tuning for alignment and other improvements, let us consider causes at both stages.

The volume of the pre-training data corpus is enormous, as it is supposed to represent world knowledge in all available written forms. Data crawled from the public Internet is the most common choice and thus out-of-date, missing, or incorrect information is expected. As the model may incorrectly memorize this information by simply maximizing the log-likelihood, we would expect the model to make mistakes.

Fine-tuning a pre-trained LLM via supervised fine-tuning and RLHF is a common technique for improving certain capabilities of the model like instruction following. Introducing new knowledge at the fine-tuning stage is hard to avoid.

Fine-tuning usually consumes much less compute, making it debatable whether the model can reliably learn new knowledge via small-scale fine-tuning. Gekhman et al. 2024 studied the research question of whether fine-tuning LLMs on new knowledge encourages hallucinations. They found that (1) LLMs learn fine-tuning examples with new knowledge slower than other examples with knowledge consistent with the pre-existing knowledge of the model; (2) Once the examples with new knowledge are eventually learned, they increase the model’s tendency to hallucinate.

Given a closed-book QA dataset (i.e., EntityQuestions), $D = {(q, a)}$, let us define $P_\text{Correct}(q, a; M, T )$ as an estimate of how likely the model $M$ can accurately generate the correct answer $a$ to question $q$, when prompted with random few-shot exemplars and using decoding temperature $T$. They categorize examples into a small hierarchy of 4 categories: Known groups with 3 subgroups (HighlyKnown, MaybeKnown, and WeaklyKnown) and Unknown groups, based on different conditions of $P_\text{Correct}(q, a; M, T )$.

Some interesting observations of the experiments, where dev set accuracy is considered a proxy for hallucinations.

These empirical results from Gekhman et al. (2024) point out the risk of using supervised fine-tuning for updating LLMs’ knowledge.

To quantify model hallucinations, Lee et al. (2022) introduced a new benchmark dataset, FactualityPrompt, consisting of both factual and nonfactual prompts. This dataset uses Wikipedia documents or sentences as the knowledge base for factuality grounding. The Wikipedia documents are known ground-truth from the FEVER dataset, and the sentences are selected based on tf-idf or sentence embedding-based similarity.

Given the model continuation and paired Wikipedia text, two evaluation metrics for hallucination are considered:

Lower NE errors and higher entailment ratios indicate higher factuality, and both metrics are found to be correlated with human annotations. Larger models are found to perform better on this benchmark.

FActScore (Factual precision in Atomicity Score; Min et al. 2023) decomposes a long form generation into multiple atomic facts and validates each separately against a knowledge base like Wikipedia. Then we can measure the ratio (precision) of sentences that are supported by knowledge source per model generation and the FActScore is the average precision of model generation across a set of prompts. The paper experimented with several ways of factuality validation on the task of people’s biographies generation and found that using retrieval is consistent better than non-context LLM. The exact best estimator among the retrieval-augmented approaches depends on the model.

Some interesting observations on model hallucination behavior:

Wei et al. (2024) proposed an evaluation method for checking long-form factuality in LLMs, named SAFE (Search-Augmented Factuality Evaluator; code). The main difference compared to FActScore is that for each self-contained, atomic fact, SAFE uses a language model as an agent to iteratively issue Google Search queries in a multi-step process and reason about whether the search results support or do not support the fact. In each step, the agent generates a search query based on a given fact to check, as well as previously obtained search results. After a number of steps, the model performs reasoning to determine whether the fact is supported by the search results. According to the experiments, SAFE approach works better than human annotators despite of 20x cheaper: 72% agreement rate with humans and 76% win rate over humans when they disagree.

The SAFE evaluation metric is F1 @ K. The motivation is that model response for long-form factuality should ideally hit both precision and recall, as the response should be both

Given the model response $y$, the metric F1 @ K is defined as:

FacTool (Chern et al. 2023) follows a standard fact checking workflow. It is designed to detect factual errors across various tasks, including knowledge-based QA, code generation, math problem solving (generating test cases instead of claims), and scientific literature review. It follows

SelfCheckGPT (Manakul et al. 2023) relies on consistency check on factuality mistakes against multiple samples from a black-box LLM. Considering that grey-box fact checking measurement needs access to token-level logprob of LLMs, SelfCheckGPT only requires samples with no dependency on external knowledge base, so black-box access is sufficient and no external knowledge base is needed.

The method works with different metrics to measure the consistency between the model response and each of the other stochastic model samples, including BERTScore, NLI, prompting (asking yes/no), etc. SelfCheckGPT with prompting seems to work out the best, when experimenting on GPT-3 generated WikiBio passages.

Prompting the model to generate responses to questions that are unanswerable or unknown could trigger hallucination. TruthfulQA (Lin et al. 2021) and SelfAware (Yin et al. 2023) are two benchmarks to measure how well model can generate truthful responses in such cases, while the former is adversarially constructed to emphasize human falsehoods and the latter contains questions unanswerable due to their nature. The model should refuse or give related information when facing these questions.

Testing questions in TruthfulQA (Lin et al. 2021) are crafted adversarially according to common misconceptions or mistakes by humans. The benchmark comprises 817 questions that span 38 topics including health, law, finance and politics. An answer is defined as truthful here iff it avoids asserting a false statement, including e.g. refusal, irrelevant truthful answers. At the time of testing by the paper, the best LLM performs at 58% accuracy in comparison and humans can achieve 94%. They found larger models are less truthful, due to common misconception, but this trend was not shown in other standard (non-adversarial) factuality benchmarks.

Examples of false answers from GPT-3 on TruthfulQA:

Yin et al. (2023) studies the concept of self-knowledge, referring to whether language models know what they know or don’t know. SelfAware, containing 1,032 unanswerable questions across five categories and 2,337 answerable questions. Unanswerable questions are sourced from online forums with human annotations while answerable questions are sourced from SQuAD, HotpotQA and TriviaQA based on text similarity with unanswerable questions. A question may be unanswerable due to various reasons, such as no scientific consensus, imaginations of the future, completely subjective, philosophical reasons that may yield multiple responses, etc. Considering separating answerable vs unanswerable questions as a binary classification task, we can measure F1-score or accuracy and the experiments showed that larger models can do better at this task.

Another way to assess the model’s awareness of unknown knowledge is to measure the model’s output uncertainty. When a question is in-between known and unknown, the model is expected to demonstrate the right level of confidence.

The experiment by Kadavath et al. (2022) showed that LLMs are shown to be well calibrated in their estimation probabilities of answer correctness on diverse multiple choice questions in a format with visible lettered answer options (MMLU, TruthfulQA, QuALITY, LogiQA), meaning that the predicted probability coincides with the frequency of that answer being true. RLHF fine-tuning makes the model poorly calibrated, but higher sampling temperature leads to better calibration results.

Lin et al. (2022) used the CalibratedMath suite of tasks. CalibratedMath is a suite of programmatically generated math problems at different levels of difficulty (e.g. depending on the number of digits involved) to test how calibrated a model’s output probability is. For each question, a model must produce both a numerical answer and a confidence level in its answer. Three types of probabilities are considered:

Agrawal et al. (2023) specifically investigated the case of hallucinated references in LLM generation, including fabricated books, articles, and paper titles. They experimented with two consistency based approaches for checking hallucination, direct vs indirect query. Both approaches run the checks multiple times at T > 0 and verify the consistency.

Direct query asks the model to judge whether a generated reference exists. Indirect query instead asks for auxiliary details—who are the authors—for the generated reference; e.g. If we want to check "Is the following paper real?", we can check "Who are the author of the paper?" Hypothesis is that the likelihood of multiple generations agreeing on the same authors for a hallucinated reference would be smaller than the likelihood of multiple responses to an direct query indicating that the reference exists. Experiments showed that indirect query approach works better and larger model are more capable and can hallucinate less.

Let’s review a set of methods to improve factuality of LLMs, ranging from retrieval of external knowledge base, special sampling methods to alignment fine-tuning. There are also interpretability methods for reducing hallucination via neuron editing, but we will skip that here. I may write about interpretability in a separate post later.

RAG (Retrieval-augmented Generation) is a very common approach to provide grounding information, that is to retrieve relevant documents and then generate with related documents as extra context.

RARR (“Retrofit Attribution using Research and Revision”; Gao et al. 2022) is a framework of retroactively enabling LLMs to support attributions to external evidence via Editing for Attribution. Given a model generated text $x$, RARR processes in two steps, outputting a revised text $y$ and an attribution report $A$ :

When evaluating the revised text $y$, both attribution and preservation metrics matter.

Similar to RARR using search + editing, FAVA (“Factuality Verification with Augmented Knowledge”; Mishra et al. 2024) also retrieves relevant documents and then edits the model output to avoid hallucination errors. The FAVA model consists of a retriever $\mathcal{M}_\text{ret}$ and an editor $\mathcal{M}_\text{edit}$.

RARR does not require training, but the editor model $\mathcal{M}_\text{edit}$ in FAVA needs to be fine-tuned. Following a more detailed taxonomy of categorizing different types of hallucination errors, we can generate synthetic training data for $\mathcal{M}_\text{edit}$ by inserting random errors into the model generation. Each example is a triplet $(c, y, y^*)$ where $c$ is the original Wikipedia paragraph as the gold context, $y$ is LM output with errors, and $y^∗$ is an output with error tags and correct editing.

Rethinking with retrieval (RR; He et al. 2022) methods relies on retrieval of relevant external knowledge as well, but no additional editing. Instead of utilizing a search query generation model, RR’s retrieval is based on decomposed CoT prompting. Given an input prompt $Q$, RR uses CoT prompting to generate multiple reasoning paths ${R_1, \dots, R_N}$ at temperature > 0, where each $R_i$ reasoning path contains an explanation $E_i$ (i.e. reasoning portion) followed by a prediction $P_i$ (i.e. the actual model output). The external knowledge $K_1, \dots, K_M$ is retrieved to support each explanation. Then we select the most faithful answer $\hat{P}$ based on how well it fits retrieved knowledge $K_1, \dots, K_M$.

Self-RAG (“Self-reflective retrieval-augmented generation”; Asai et al. 2024) trains a LM end-to-end to learn to reflect on its own generation by outputting both task output and intermittent special reflection tokens. They created a supervision dataset for a critic model and a generator model by prompting GPT-4 and then distilled that into an in-house model to reduce inference cost.

Given the input prompt $x$, the generated output $y$ consists of multiple segments (e.g. one segment is one sentence) $y=[y_1, \dots, y_T]$. There are four type of reflection tokens in total, one for retrieval and three for critique:

Self-RAG generates one segment of $y_t$ at one time. Given $x$ and the proceeding generation $y_{<t}$, the model decodes the Retrieve token:

Without grounding by external retrieved knowledge, we can design a process for using the model itself to do verification and revision to reduce hallucination.

Dhuliawala et al. (2023) proposed a method named Chain-of-Verification (CoVe) based on a chain of actions to plan and execute verification. CoVe consists of four core steps:

CoVe is designed this ways because using long-form chain-of-verification generation may result in repeated hallucination because the initial hallucinated response is still in the context and can be attended to during the new generation, whereas answering individual verification questions separately leads to better results than long-form generation.

Here are some interesting observations from the CoVe experiments:

RECITE (“Recitation-augmented generation”; Sun et al. 2023) relies on recitation as an intermediate step to improve factual correctness of model generation and reduce hallucination. The motivation is to utilize Transformer memory as an information retrieval mechanism. Within RECITE’s recite-and-answer scheme, the LLM is asked to first recite relevant information and then generate the output. Precisely, we can use few-shot in-context prompting to teach the model to generate recitation and then generate answers conditioned on recitation. Further it can be combined with self-consistency ensemble consuming multiple samples and extended to support multi-hop QA.

The generated recitation is comparable with the BM25 based retrieval model, but both have gaps with the use of ground truth passage. According to their error analysis, about 7-10% questions have the correct recitation but cannot produce the correct answer, while around 12% questions do not have the correct recitation but can be answered correctly anyway.

Lee, et al. (2022) found that nucleus sampling (top-$p$ sampling) is found to perform worse on FactualityPrompt benchmark than greedy sampling, although it achieves better diversity and less repetition, since nucleus sampling added extra randomness. So they proposed factual-nucleus sampling algorithm, based on the hypothesis that sampling randomness does more harm to factuality at the latter part of the sentence than at the beginning. Factual-nucleus sampling is designed to dynamically adapt the probability $p$ during sampling tokens for each sentence. For the $t$-th token in one sentence, we have $p_t = \max(\omega, p \cdot \lambda^{t−1})$ where $\omega$ is to prevent the sampling falls back to greedy that hurts generation quality and diversity.

Inference-Time Intervention (ITI; Li et al. 2023) investigated whether certain attention heads are more correlated with factuality by fitting a linear probe on the activations in each layer to discriminate between truthful vs false outputs. They found for many heads, the probes cannot do better than random, while some show strong performance. After identifying a sparse set of attention heads with high linear probing accuracy for truthfulness, at inference time ITI shifts activations of top $K$ selected attention heads along the “truthful” direction.

Lee, et al. (2022) proposed two ideas for factuality-enhanced training:

Lin et al. (2024) proposed to do run SFT + RLHF alignment training with special focus on factuality, named FLAME (“Factuality-Aware Alignment”).

To avoid accidentally distilling unknown knowledge into the model during alignment training, they suggested using the model generated responses to form SFT / DPO datasets.

Factuality tuning (Tian & Mitchell et al. 2024) also relies on fine-tuning language models for better factuality. They experimented with different ways of truthfulness estimation of atomic claims in each model sample and then run DPO

Process of factuality tuning:

Assigning attribution in the model outputs when generating conditions on search results is a good way to reduce hallucination. There is a branch of work to train LLMs to better consume retrieved content and assign high-quality attributions.

WebGPT (Nakano, et al. 2022) combines web search for document retrieval with a fine-tuned GPT model, aiming to answer long-form questions to reduce hallucination and achieve better factual accuracy. The model interacts with the Internet search in a text-based Web browser and learns to answer with references to web pages. While the model is browsing, one of the actions it can take is to quote an extract from the current page. When this is performed, the page title, domain name and extract are recorded to be used later as a reference. The center of WebGPT is to use references to assist humans to judge factual correctness.

The model is first supervised fine-tuned on demonstrations of humans using the web-browsing environment to answer questions for behavior cloning. Comparison data is collected between two model-generated answers to the same question (each with their own set of references), where answers are judged for their factual accuracy, coherence, and overall usefulness. Reward model is used for RL training and best-of-n rejection sampling. RL training and best-of-n rejection sampling. In comparison, RL only introduces a small benefit and it is even smaller when rejection sampling is used.

GopherCite (Menick et al. 2022) is quite similar to WebGPT on using search engine to create support materials and teaching models to provide references. Both run supervised fine-tuning for bootstrapping and both apply RL training from human preference. But different from WebGPT that depends on human demonstration for behavior cloning, GopherCite generates demonstrations via few-shot prompting and each generation uses context stuffing with relevant documents and then use reward model to score which ones are the best.

One additional trick to avoid low quality response is to configure the model to decline to answer with a canned answer "I don't know", decided by a global RM threshold, known as selective prediction.

The empirical results on RL is similar to WebGPT in that RL only brings in limited improvement or no improvement when combined with rejection sampling.

Here is a list of datasets mentioned in this post.

TruthfulQA (Lin et al. 2021) is designed to measure how well a LLM can generate truthful responses. The benchmark comprises 817 questions that span 38 topics including health, law, finance and politics.

FactualityPrompt (Lee, et al. 2022) is a benchmark consisting of both factual and nonfactual prompts. It relies on Wikipedia documents or sentences as the knowledge base for factuality grounding.

SelfAware (Yin et al. 2023) contains 1,032 unanswerable questions across five categories and 2,337 answerable questions. Unanswerable questions are sourced from online forums with human annotations while answerable questions are sourced from SQuAD, HotpotQA and TriviaQA based on text similarity with unanswerable questions.

LongFact (Wei et al. 2024 ) is designed for checking long-form generation factuality. It consists of 2280 fact-seeking prompts that seek long-form responses on 38 manually curated topics

HaDes (Liu et al. 2021) is a benchmark for hallucination detection as a binary classification task. The dataset is created by perturbing Wikipedia text and human annotation.

FEVER (Fact Extraction and VERification) dataset contains 185,445 claims generated by altering sentences extracted from Wikipedia and subsequently verified without knowledge of the sentence they were derived from. Each claim is classified as Supported, Refuted or NotEnoughInfo.

FAVABench (Mishra et al. 2024) is a benchmark for evaluating fine-grained hallucination. There are 200 information-seeking source prompts and 3 model responses per prompt, resulting in 600 responses in total. Each model response is manually labeled with fine-grained annotations on hallucination error types.

Cited as:

Weng, Lilian. (Jul 2024). Extrinsic Hallucinations in LLMs. Lil’Log. https://lilianweng.github.io/posts/2024-07-07-hallucination/.

Or

[1] Ji et al. “Survey of hallucination in natural language generation.” ACM Computing Surveys (2022)

[2] Gekhman et al. “Does Fine-Tuning LLMs on New Knowledge Encourage Hallucinations?” arXiv preprint arXiv:2405.05904 (2024).

[3] Min et al. “FActScore: Fine-grained atomic evaluation of factual precision in long form text generation.” EMNLP 2023.

[4] Wei et al. 2024 “Long-form Factuality in LLMs” arXiv preprint arXiv:2403.18802 (2024).

[5] Chern et al. “FacTool: Factuality detection in generative AI - a tool augmented framework for multi-task and multi-domain scenarios.” arXiv preprint arXiv:2307.13528 (2023).

[6] Lin et al. “TruthfulQA: Measuring How Models Mimic Human Falsehoods.” ACL 2022.

[7] Yin et al. “Do Large Language Models Know What They Don’t Know?” ACL 2023.

[8] Kadavath et al. “Language Models (Mostly) Know What They Know” arXiv preprint arXiv:2207.05221 (2022).

[9] Agrawal et al. “Do language models know when they’re hallucinating references?” arXiv preprint arXiv:2305.18248 (2023).

[10] Lin et al. “Teaching Models to Learn Uncertainty in Words.” arXiv preprint arXiv:2205.14334 (2022).

[11] Gao et al. “RARR: Researching and Revising What Language Models Say, Using Language Models.” ACL 2023.

[12] He et al. “Rethinking with retrieval: Faithful large language model inference.” arXiv preprint arXiv:2301.00303 (2022).

[13] Asai et al. “Self-RAG: Learning to retrieve, generate and critique through self-reflection.” ICLR 2024.

[14] Mishra et al. “Fine-grained Hallucination Detection and Editing for Language Models.” arXiv preprint arXiv:2401.06855 (2024).

[15] Lee, et al. “Factuality Enhanced Language Models for Open-Ended Text Generation.” NeuriPS 2022.

[16] Manakul et al. “SelfCheckGPT: Zero-Resource Black-Box Hallucination Detection for Generative Large Language Models.” EMNLP 2023.

[17] Li et al. “Inference-Time Intervention: Eliciting Truthful Answers from a Language Model.” NeuriPS 2023.

[18] Chuang et al. “DoLa: Decoding by contrasting layers improves factuality in large language models.” ICLR 2024.

[19] Dhuliawala et al. “Chain-of-Verification Reduces Hallucination in Large Language Models.” arXiv preprint arXiv:2309.11495 (2023).

[20] Sun et al. “Recitation-Augmented Language Models.” ICLR 2023.

[21] Lin et al. “FLAME: Factuality-Aware Alignment for Large Language Models.” arXiv preprint arXiv:2405.01525 (2024).

[22] Tian & Mitchell et al. “Fine-tuning Language Models for Factuality.” ICLR 2024. (code)

[23] Nakano, Hilton & Balaji, et al. “WebGPT: Browser-assisted question-answering with human feedback.” arXiv preprint arXiv:2112.09332 (2021).

[24] Menick et al. “Teaching language models to support answers with verified quotes.” arXiv preprint arXiv:2203.11147 (2022).

---

## [Diffusion Models for Video Generation](https://lilianweng.github.io/posts/2024-04-12-diffusion-video/)

Diffusion models have demonstrated strong results on image synthesis in past years. Now the research community has started working on a harder task—using it for video generation. The task itself is a superset of the image case, since an image is a video of 1 frame, and it is much more challenging because:

🥑 Required Pre-read: Please make sure you have read the previous blog on “What are Diffusion Models?” for image generation before continue here.

First let’s review approaches for designing and training diffusion video models from scratch, meaning that we do not rely on pre-trained image generators.

Here we use a slightly different variable definition from the previous post, but the math stays the same. Let $\mathbf{x} \sim q_\text{real}$ be a data point sampled from the real data distribution. Now we are adding Gaussian noise in small amount in time, creating a sequence of noisy variations of $\mathbf{x}$, denoted as $\{\mathbf{z}_t \mid t =1 \dots, T\}$, with increasing amount of noise as $t$ increases and the last $q(\mathbf{z}_T) \sim \mathcal{N}(\mathbf{0}, \mathbf{I})$. The noise-adding forward process is a Gaussian process. Let $\alpha_t, \sigma_t$ define a differentiable noise schedule of the Gaussian process:

To represent $q(\mathbf{z}_t \vert \mathbf{z}_s)$ for $0 \leq s < t \leq T$, we have:

Let the log signal-to-noise-ratio be $\lambda_t = \log[\alpha^2_t / \sigma^2_t]$, we can represent the DDIM (Song et al. 2020) update as:

There is a special $\mathbf{v}$-prediction ($\mathbf{v} = \alpha_t \boldsymbol{\epsilon} - \sigma_t \mathbf{x}$) parameterization, proposed by Salimans & Ho (2022). It has been shown to be helpful for avoiding color shift in video generation compared to $\boldsymbol{\epsilon}$-parameterization.

The $\mathbf{v}$-parameterization is derived with a trick in the angular coordinate. First, we define $\phi_t = \arctan(\sigma_t / \alpha_t)$ and thus we have $\alpha_\phi = \cos\phi, \sigma_t = \sin\phi, \mathbf{z}_\phi = \cos\phi \mathbf{x} + \sin\phi\boldsymbol{\epsilon}$. The velocity of $\mathbf{z}_\phi$ can be written as:

Then we can infer,

The DDIM update rule is updated accordingly,

The $\mathbf{v}$-parameterization for the model is to predict $\mathbf{v}_\phi = \cos\phi\boldsymbol{\epsilon} -\sin\phi\mathbf{x} = \alpha_t\boldsymbol{\epsilon} - \sigma_t\mathbf{x}$.

In the case of video generation, we need the diffusion model to run multiple steps of upsampling for extending video length or increasing the frame rate. This requires the capability of sampling a second video $\mathbf{x}^b$ conditioned on the first $\mathbf{x}^a$, $\mathbf{x}^b \sim p_\theta(\mathbf{x}^b \vert \mathbf{x}^a)$, where $\mathbf{x}^b$ might be an autoregressive extension of $\mathbf{x}^a$ or be the missing frames in-between for a video $\mathbf{x}^a$ at a low frame rate.

The sampling of $\mathbf{x}_b$ needs to condition on $\mathbf{x}_a$ besides its own corresponding noisy variable. Video Diffusion Models (VDM; Ho & Salimans, et al. 2022) proposed the reconstruction guidance method using an adjusted denoising model such that the sampling of $\mathbf{x}^b$ can be properly conditioned on $\mathbf{x}^a$:

where $\hat{\mathbf{x}}^a_\theta (\mathbf{z}_t), \hat{\mathbf{x}}^b_\theta (\mathbf{z}_t)$ are reconstructions of $\mathbf{x}^a, \mathbf{x}^b$ provided by the denoising model. And $w_r$ is a weighting factor and a large one $w_r >1$ is found to improve sample quality. Note that it is also possible to simultaneously condition on low resolution videos to extend samples to be at the high resolution using the same reconstruction guidance method.

Similar to text-to-image diffusion models, U-net and Transformer are still two common architecture choices. There are a series of diffusion video modeling papers from Google based on the U-net architecture and a recent Sora model from OpenAI leveraged the Transformer architecture.

VDM (Ho & Salimans, et al. 2022) adopts the standard diffusion model setup but with an altered architecture suitable for video modeling. It extends the 2D U-net to work for 3D data (Cicek et al. 2016), where each feature map represents a 4D tensor of frames x height x width x channels. This 3D U-net is factorized over space and time, meaning that each layer only operates on the space or time dimension, but not both:

Imagen Video (Ho, et al. 2022) is constructed on a cascade of diffusion models to enhance the video generation quality and upgrades to output 1280x768 videos at 24 fps. The Imagen Video architecture consists of the following components, counting 7 diffusion models in total.

The base denoising models performs spatial operations over all the frames with shared parameters simultaneously and then the temporal layer mixes activations across frames to better capture temporal coherence, which is found to work better than frame-autoregressive approaches.

Both SSR and TSR models condition on the upsampled inputs concatenated with noisy data $\mathbf{z}_t$ channel-wise. SSR upsamples by bilinear resizing, while TSR upsamples by repeating the frames or filling in blank frames.

Imagen Video also applies progressive distillation to speed up sampling and each distillation iteration can reduce the required sampling steps by half. Their experiments were able to distill all 7 video diffusion models down to just 8 sampling steps per model without any noticeable loss in perceptual quality.

To achieve better scaling efforts, Sora (Brooks et al. 2024) leverages DiT (Diffusion Transformer) architecture that operates on spacetime patches of video and image latent codes. Visual input is represented as a sequence of spacetime patches which act as Transformer input tokens.

Another prominent approach for diffusion video modeling is to “inflate” a pre-trained image-to-text diffusion model by inserting temporal layers and then we can choose to only fine-tune new layers on video data, or avoid extra training at all. The prior knowledge of text-image pairs is inherited by the new model and thus it can help alleviate the requirement on text-video pair data.

Make-A-Video (Singer et al. 2022) extends a pre-trained diffusion image model with a temporal dimension, consisting of three key components:

The final video inference scheme can be formulated as:

where:

Spatiotemporal SR layers contain pseudo-3D convo layers and pseudo-3D attention layers:

They can be represented as:

where an input tensor $\mathbf{h} \in \mathbb{R}^{B\times C \times F \times H \times W}$ (corresponding to batch size, channels, frames, height and weight); and $\circ T$ swaps between temporal and spatial dimensions; $\text{flatten}(.)$ is a matrix operator to convert $\mathbf{h}$ to be $\mathbf{h}’ \in \mathbb{R}^{B \times C \times F \times HW}$ and $\text{flatten}^{-1}(.)$ reverses that process.

During training, different components of Make-A-Video pipeline are trained independently.

Tune-A-Video (Wu et al. 2023) inflates a pre-trained image diffusion model to enable one-shot video tuning: Given a video containing $m$ frames, $\mathcal{V} = \{v_i \mid i = 1, \dots, m\}$, paired with a descriptive prompt $\tau$, the task is to generate a new video $\mathcal{V}^*$ based on a slightly edited & related text prompt $\tau^*$. For example, $\tau$ = "A man is skiing" can be extended to $\tau^*$="Spiderman is skiing on the beach". Tune-A-Video is meant to be used for object editing, background change, and style transfer.

Besides inflating the 2D convo layer, the U-Net architecture of Tune-A-Video incorporates the ST-Attention (spatiotemporal attention) block to capture temporal consistency by querying relevant positions in previous frames. Given latent features of frame $v_i$, previous frames $v_{i-1}$ and the first frame $v_1$ are projected to query $\mathbf{Q}$, key $\mathbf{K}$ and value $\mathbf{V}$, the ST-attention is defined as:

Gen-1 model (Esser et al. 2023) by Runway targets the task of editing a given video according to text inputs. It decomposes the consideration of structure and content of a video $p(\mathbf{x} \mid s, c)$ for generation conditioning. However, to do a clear decomposition of these two aspects is not easy.

The architecture changes in Gen-1 are quite standard, i.e. adding 1D temporal convo layer after each 2D spatial convo layer in its residual blocks and adding 1D temporal attention block after each 2D spatial attention block in its attention blocks. During training, the structure variable $s$ is concatenated with the diffusion latent variable $\mathbf{z}$, where the content variable $c$ is provided in the cross-attention layer. At inference time, the clip embedding is converted via a prior to convert CLIP text embedding to be CLIP image embedding.

Video LDM (Blattmann et al. 2023) trains a LDM (Latent diffusion models) image generator first. Then the model is fine-tuned to produce videos with a temporal dimension added. The fine-tuning only applies to these newly added temporal layers on encoded image sequences. The temporal layers $\{l^i_\phi \mid i = \ 1, \dots, L\}$ in the Video LDM (See Fig. 10) are interleaved with existing spatial layers $l^i_\theta$ which stays frozen during fine-tuning. That’s being said, we only fine-tune the new parameters $\phi$ but not the pre-trained image backbone model parameters $\theta$. The pipeline of Video LDM first generates key frames at low fps and then processes through 2 steps of latent frame interpolations to increase fps.

The input sequence of length $T$ is interpreted as a batch of images (i.e. $B \cdot T$) for the base image model $\theta$ and then gets reshaped into video format for $l^i_\phi$ temporal layers. There is a skip connection leads to a combination of temporal layer output $\mathbf{z}’$ and the spatial output $\mathbf{z}$ via a learned merging parameter $\alpha$. There are two types of temporal mixing layers implemented in practice: (1) temporal attention and (2) residual blocks based on 3D convolutions.

However, there is a remaining issue with LDM’s pretrainined autoencoder which only sees images never videos. Naively using that for video generation can cause flickering artifacts without good temporal coherence. So Video LDM adds additional temporal layers into the decoder and fine-tuned on video data with a patch-wise temporal discriminator built from 3D convolutions, while the encoder remains unchanged so that we still can reuse the pretrained LDM. During temporal decoder fine-tuning, the frozen encoder processes each frame in the video independently, and enforce temporally coherent reconstructions across frames with a video-aware discriminator.

Similar to Video LDM, the architecture design of Stable Video Diffusion (SVD; Blattmann et al. 2023) is also based on LDM with temporal layers inserted after every spatial convolution and attention layer, but SVD fine-tunes the entire model. There are three stages for training video LDMs:

SVD specially emphasizes the critical role of dataset curation in model performance. They applied a cut detection pipeline to get more cuts per video and then applied three different captioner models: (1) CoCa for mid-frame, (2) V-BLIP for a video caption, and (3) LLM based captioning based on previous two captions. Then they were able to continue to improve video datasets, by removing clips with less motion (filtered by low optical flow scores calculated at 2 fps), excessive text presence (apply optical character recognition to identify videos with lots of text), or generally low aesthetic value (annotate the first, middle, and last frames of each clip with CLIP embeddings and calculate aesthetics scores & text-image similarities). The experiments showed that a filtered, higher quality dataset leads to better model quality, even when this dataset is much smaller.

The key challenge of generating distant key frames first and then adding interpolation with temporal super-resolution is how to maintain high-quality temporal consistency. Lumiere (Bar-Tal et al. 2024) instead adopts a space-time U-Net (STUNet) architecture that generates the entire temporal duration of the video at once through a single pass, removing the dependency on TSR (temporal super-resolution) components. STUNet downsamples the video in both time and space dimensions and thus expensive computation happens in a compact time-space latent space.

STUNet inflates a pretrained text-to-image U-net to be able to downsample and upsample videos at both time and space dimensions. Convo-based blocks consist of pre-trained text-to-image layers, followed by a factorized space-time convolution. And attention-based blocks at the coarsest U-Net level contains the pre-trained text-to-image, followed by temporal attention. Further training only happens with the newly added layers.

Somehow surprisingly, it is possible to adapt a pre-trained text-to-image model to output videos without any training 🤯.

If we naively sample a sequence of latent codes at random and then construct a video of decoded corresponding images, there is no guarantee in the consistency in objects and semantics in time. Text2Video-Zero (Khachatryan et al. 2023) enables zero-shot, training-free video generation by enhancing a pre-trained image diffusion model with two key mechanisms for temporal consistency:

The process of sampling a sequence of latent variables, $\mathbf{x}^1_T, \dots, \mathbf{x}^m_T$, with motion information is described as follows:

Besides, Text2Video-Zero replaces the self-attention layer in a pre-trained SD model with a new cross-frame attention mechanism with reference to the first frame. The motivation is to preserve the information about the foreground object’s appearance, shape, and identity throughout the generated video.

Optionally, the background mask can be used to further smoothen and improve background consistency. Let’s say, we obtain a corresponding foreground mask $\mathbf{M}_k$ for the $k$-th frame using some existing method, and background smoothing merges the actual and the warped latent code at the diffusion step $t$, w.r.t. the background matrix:

where $\mathbf{x}^k_t$ is the actual latent code and $\tilde{\mathbf{x}}^k_t$ is the warped latent code on the background; $\alpha$ is a hyperparameter and the papers set $\alpha=0.6$ in the experiments.

Text2video-zero can be combined with ControlNet where the ControlNet pretrained copy branch is applied per frame on each $\mathbf{x}^k_t$ for $k = 1, \dots, m$ in each diffusion time-step $t = T , \dots, 1$ and add the ControlNet branch outputs to the skip-connections of the main U-net.

ControlVideo (Zhang et al. 2023) aims to generate videos conditioned on text prompt $\tau$ and a motion sequence (e.g., depth or edge maps), $\mathbf{c} = \{c^i\}_{i=0}^{N-1}$. It is adapted from ControlNet with three new mechanisms added:

Cited as:

Weng, Lilian. (Apr 2024). Diffusion Models Video Generation. Lil’Log. https://lilianweng.github.io/posts/2024-04-12-diffusion-video/.

Or

[1] Cicek et al. 2016. “3D U-Net: Learning Dense Volumetric Segmentation from Sparse Annotation.”

[2] Ho & Salimans, et al. “Video Diffusion Models.” 2022 | webpage

[3] Bar-Tal et al. 2024 “Lumiere: A Space-Time Diffusion Model for Video Generation.”

[4] Brooks et al. “Video generation models as world simulators.” OpenAI Blog, 2024.

[5] Zhang et al. 2023 “ControlVideo: Training-free Controllable Text-to-Video Generation.”

[6] Khachatryan et al. 2023 “Text2Video-Zero: Text-to-image diffusion models are zero-shot video generators.”

[7] Ho, et al. 2022 “Imagen Video: High Definition Video Generation with Diffusion Models.”

[8] Singer et al. “Make-A-Video: Text-to-Video Generation without Text-Video Data.” 2022.

[9] Wu et al. “Tune-A-Video: One-Shot Tuning of Image Diffusion Models for Text-to-Video Generation.” ICCV 2023.

[10] Blattmann et al. 2023 “Align your Latents: High-Resolution Video Synthesis with Latent Diffusion Models.”

[11] Blattmann et al. 2023 “Stable Video Diffusion: Scaling Latent Video Diffusion Models to Large Datasets.”

[12] Esser et al. 2023 “Structure and Content-Guided Video Synthesis with Diffusion Models.”

[13] Bar-Tal et al. 2024 “Lumiere: A Space-Time Diffusion Model for Video Generation.”

---

