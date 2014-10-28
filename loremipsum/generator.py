"""
This module provides a simple class to generate plausible text paragraphs,
sentences, or just random words out of a sample text and a sample lexicon.
"""

from __future__ import unicode_literals
import collections
import contextlib
import math
import random
import re

from loremipsum.serialization import schemes

__all__ = ['Generator', 'Sample']

# Python 3 compatibility: __builtins__ turned to a module so access to get
# method whould raise AttributeError
try:
    unicode_str = __builtins__.get('unicode')
    irange = __builtins__.get('xrange')
    urlparse = __import__('urlparse').urlparse
except AttributeError:
    unicode_str = str
    irange = range
    urlparse = __import__('urllib.parse', fromlist=['urllib']).urlparse


def _mean(values):
    """Calculate the mean value of a list of integers."""
    return sum(values) / float(len(values))


def _sigma(values):
    """Calculate the sigma value of a list of integers."""
    return math.sqrt(_mean([v ** 2 for v in values]) - _mean(values) ** 2)


class Sample(object):
    """The sample that generated sentences are based on.

    Sentences are generated so that they will have a similar distribution
    of word, sentence and paragraph lengths and punctuation.

    Sample text should be a string consisting of a number of paragraphs,
    each separated by empty lines. Each paragraph should consist of a
    number of sentences, separated by periods, exclamation marks and/or
    question marks. Sentences consist of words, separated by white space.

    :param tuple frozen:                An immutable representation of the
                                        sample imformations. This argument
                                        takes precedence over sample, text,
                                        lexicon, word_delimiters or
                                        sentence_delimiters.
    :param dict sample:                 A dictionary of the sample informations.
                                        This argument takes precedence over
                                        sample, lexicon, word_delimiters or
                                        sentence_delimiters.
    :param str text:                    A string containing the sample text.
                                        Sample text must contain one or more
                                        empty-line delimited paragraphs. Each
                                        paragraph must contain one or more
                                        sentences, delimited by any char
                                        included in the sentence_delimiters
                                        param.
    :param str lexicon:                 A list of strings to be used as words.
    :param str word_delimiters:         A string of chars used as word
                                        delimiters.
    :param str sentence_delimiters:     A string of chars used as sentence
                                        delimiters.
    :raises TypeError:                  If neither frozen nor sample are
                                        provided and any of text, lexicon,
                                        word_delimiters or sentence_delimiters
                                        are missing.
    :raises ValueError:                 If could not succesfully create an
                                        internal :py:class:`Sample` out of the
                                        supplied arguments.
    """

    def __init__(self, **args):
        frozen = args.get('frozen')
        sample = args.get('sample')
        text = args.get('text')
        lexicon = args.get('lexicon')
        word_delimiters = args.get('word_delimiters')
        sentence_delimiters = args.get('sentence_delimiters')
        ingredients = [text, lexicon, word_delimiters, sentence_delimiters]
        if frozen:
            self._reheat(frozen)
        elif sample:
            if isinstance(sample, self.__class__):
                self._s = sample._s.copy()
            else:
                self._s = dict()
                self._s.update(sample)
        elif all(ingredients):
            self._cook(*ingredients)
        else:
            raise TypeError('Missing argument')
        self._hash = hash(self.frozen())

    def _cook(self, text, lexicon, word_delimiters, sentence_delimiters):

        paragraphs_lens = list()
        sentences_lens = list()
        previous = (0, 0)

        us = lambda s: unicode_str(s).strip('\n')
        self._s = {
            'text': us(text),
            'lexicon': us(lexicon),
            'word_delimiters': us(word_delimiters),
            'sentence_delimiters': us(sentence_delimiters)}

        # Chains of three words that appear in the sample text
        # Maps a pair of word-lengths to a third word-length and an optional
        # piece of trailing punctuation (for example, a period, comma, etc.)
        self._s['chains'] = chains = collections.defaultdict(list)

        # Pairs of word-lengths that can appear at the beginning of sentences
        self._s['starts'] = starts = [previous]

        # Words that can be used in the generated output
        # Maps a word-length to a list of words of that length
        self._s['dictionary'] = dict()
        for word in self._s['lexicon'].split():
            self._s['dictionary'].setdefault(len(word), list()).append(word)

        for paragraph in self._s['text'].split('\n\n'):

            # We've got a paragraph, so prepare to count sentences.
            paragraphs_lens.append(0)

            for sentence in self._find_sentences(paragraph.strip()):

                # We've got a sentence, so prepare to count words an increas
                # paragraph length.
                sentences_lens.append(0)
                paragraphs_lens[-1] += 1

                # First sentence ever will be set as sample incipit.
                self._s.setdefault('incipit', sentence.group(0))

                # Generates the chains and starts values required for sentence
                # generation.
                for word in self._find_words(sentence.group(0)):

                    # We've got a word, so increas sentence length.
                    sentences_lens[-1] += 1

                    # Build chains and starts based on text analysis.
                    word, delimiter = word.group(0).strip(), ''
                    while word and word[-1] in self._s['word_delimiters']:
                        word, delimiter = word[:-1], word[-1]
                    if word:
                        chains[previous].append((len(word), delimiter))
                        if delimiter:
                            starts.append(previous)
                        previous = (previous[1], len(word))

        # Calculates the mean and standard deviation of the lengths of
        # sentences (in words) in a sample text.
        self._s['sentence_mean'] = _mean(sentences_lens)
        self._s['sentence_sigma'] = _sigma(sentences_lens)

        # Calculates the mean and standard deviation of the lengths of
        # paragraphs (in sentences) in a sample text.
        self._s['paragraph_mean'] = _mean(paragraphs_lens)
        self._s['paragraph_sigma'] = _sigma(paragraphs_lens)
        self._taste()

    def _reheat(self, frozen):
        _s = dict(frozen)
        _s['chains'] = dict((tuple(k), v) for k, v in _s['chains'])
        for chain, values in _s['chains'].items():
            _s['chains'][chain] = [tuple(v) for v in values]
        _s['starts'] = [tuple(s) for s in _s['starts']]
        _s['dictionary'] = dict(_s['dictionary'])
        self._s = _s
        self._taste()

    def _taste(self):
        """Self check."""

        if not self._s['dictionary']:
            raise ValueError("Invalid lexicon")
        if not self._s['chains']:
            raise ValueError("Invalid sample text")

    def _find_sentences(self, text):
        """Creates an iterator over text, which yields sentences."""
        delimiters = '\\'.join(self._s['sentence_delimiters'])
        sentences = re.compile(r'([^\\{d}])*[\\{d}]'.format(d=delimiters))
        return sentences.finditer(text.strip())

    def _find_words(self, text):
        """Creates an iterator over text, which yields words."""
        words = re.compile(r'\s*([\S]+)')
        return words.finditer(text.strip())

    @classmethod
    def cooked(class_, text, lexicon, word_delimiters, sentence_delimiters):
        return class_(
            text=text,
            lexicon=lexicon,
            word_delimiters=word_delimiters,
            sentence_delimiters=sentence_delimiters)

    @classmethod
    def thawed(class_, frozen):
        return class_(frozen=frozen)

    @classmethod
    def duplicated(class_, sample):
        return class_(sample=sample)

    def row(self):
        return (
            self._s['text'],
            self._s['lexicon'],
            self._s['word_delimiters'],
            self._s['sentence_delimiters'])

    def frozen(self):
        """Returns a frozen representation of itself.

        :rtype:     tuple of tuples
        """
        _s = self._s.copy()
        ts = lambda i: tuple(sorted(i))
        _s['chains'] = ts((k, ts(v)) for k, v in _s['chains'].items())
        _s['dictionary'] = ts((k, ts(v)) for k, v in _s['dictionary'].items())
        _s['starts'] = ts(_s['starts'])
        return ts(_s.items())

    def copy(self):
        return self._s.copy()

    @classmethod
    def load(class_, url, **args):
        """Loads a sample from a serialization medium."""
        url = urlparse(url)
        return schemes.get(url.scheme).load(class_, url, **args)

    def dump(self, url, **args):
        """Dumps a sample into a serialization medium."""
        url = urlparse(url)
        schemes.get(url.scheme).dump(self, url, **args)

    def __getitem__(self, key):
        return self._s[key]

    def __iter__(self):
        return self._s.__iter__()

    def __len__(self):
        return self._s.__len__()

    def __hash__(self):
        return hash(self.frozen())

    def __eq__(self, other):
        return self._hash == hash(other)


class Generator(object):
    """Generates random strings of plausible text.

    Markov chains are used to generate the random text based on the analysis of
    a sample text. In the analysis, only paragraph, sentence and word lengths,
    and some basic punctuation matter -- the actual words are ignored. A
    provided list of words is then used to generate the random text, so that it
    will have a similar distribution of paragraph, sentence and word lengths.

    That attributes of this class should be considered 'read-only', and even if
    you can access the internal state of the generator, you don't want to mess
    with it.
    """

    def __init__(self, sample=None):
        self._sample = sample

    @property
    def sample(self):
        return self._sample

    @sample.setter
    def sample(self, value):
        if isinstance(value, dict):
            self._sample = Sample.duplicated(value)
        elif isinstance(value, tuple):
            try:
                # If value is row it won't have cooked up keys, so KeyError
                # will be raised.
                self._sample = Sample.thawed(value)
            except ValueError:
                self._sample = Sample.cooked(*value)
        elif isinstance(value, Sample):
            self._sample = value
        else:
            raise ValueError(type(value))

    @contextlib.contextmanager
    def default(self, **args):
        """Context manager. Yields a :py:class:`Generator` with altered defaults.

        The purpose of this method is to let the call of more
        :py:class:`Generator` methods with predefined set of arguments.

        >>> from loremipsum import generator
        >>> g = generator.Generator(...)
        >>> with g.default(sentence_sigma=0.9, sentence_mean=0.9) as short:
        >>>     sentences = short.generate_sentences(3)
        >>>     paragraps = short.generate_paragraphs(5, incipit=True)
        """
        copy = self._sample._s.copy()
        copy.update(args)
        yield Generator(sample=Sample.duplicated(copy))

    def generate_word(self, length=None):
        """Selects a random word from the lexicon.

        :param int length:  the length of the generate word
        :rtype:             str or unicode or None
        """

        dictionary = self._sample['dictionary']
        if not length:
            length = random.choice(list(dictionary))
        return random.choice(dictionary.get(length, (None,)))

    def generate_words(self, amount, length=None):
        """Creates a generatator of the specified amount of words.

        Words are randomly selected from the lexicon. Also accepts length
        argument as per :py:meth:`generate_word`.

        :param int amount:  the amount of words to be generated
        :rtype:             generator
        """

        for __ in irange(amount):
            yield self.generate_word(length)

    def generate_sentence(self, **args):
        """Generates a single sentence, of random length.

        :param bool incipit:            If True, then the text will begin with
                                        the sample text incipit sentence.
        :param int sentence_len:        The length of the sentence in words.
                                        Takes precedence over sentence_mean and
                                        sentence_sigma.
        :param float sentence_mean:     Override the sentence mean value.
        :param float sentence_sigma:    Override the sentence sigma value.
        :retruns:                       A tuple containing sentence length and
                                        sentence text.
        :rtype:                         tuple(int, str or unicode)
        """

        # The length of the sentence is a normally distributed random variable.
        mean = args.get('sentence_mean', self._sample['sentence_mean'])
        sigma = args.get('sentence_sigma', self._sample['sentence_sigma'])
        incipit = args.get('incipit', False)
        random_len = int(1 + math.ceil(abs(random.normalvariate(mean, sigma))))
        sentence_len = args.get('sentence_len', random_len)
        previous_set = set(self._sample['chains']) & set(self._sample['starts'])
        words = list()
        previous = tuple()
        last_word = ''
        dictionary = self._sample['dictionary']

        # Defined here in case while loop doesn't run
        word_delimiter = ''

        # Start the sentence with sample incipit, if desired
        if incipit:
            words.extend(self.sample['incipit'].split()[:sentence_len])
            if words[-1][-1] in self.sample['word_delimiters']:
                word_delimiter = words[-1][-1]

        # Generate a sentence from the "chains"
        for __ in irange(sentence_len - len(words)):
            # If the current starting point is invalid, choose another randomly
            if previous not in self._sample['chains']:
                previous = random.sample(previous_set, 1)[0]

            # Choose the next "chain" to go to. This determines the next word
            # length we'll use, and whether there is e.g. a comma at the end of
            # the word.
            chain = random.choice(self._sample['chains'][previous])
            word_len = chain[0]

            # If the word delimiter contained in the chain is also a sentence
            # delimiter, then we don't include it because we don't want the
            # sentence to end prematurely (we want the length to match the
            # sentence_len value).
            word_delimiter = ''
            if chain[1] not in self.sample['sentence_delimiters']:
                word_delimiter = chain[1]

            # Choose a word randomly that matches (or closely matches) the
            # length we're after.
            closest = min(list(dictionary), key=lambda x: abs(x - word_len))

            # Readability. No word can appear next to itself.
            word = random.choice(dictionary[closest])
            while word == last_word and len(dictionary[closest]) > 1:
                word = random.choice(dictionary[closest])
            last_word = word

            words.append(word + word_delimiter)
            previous = (previous[1], word_len)

        # Finish the sentence off with capitalisation, a period and
        # form it into a string.
        # TODO(sentence_delimiters): should analyze sample to randomize
        #                            sentence delimiter choice.
        sentence = ' '.join(words).capitalize().rstrip(word_delimiter) + '.'
        return (len(words), sentence)

    def generate_sentences(self, amount, **args):
        """Generator method that yields sentences, of random length.

        Also accepts the same arguments as :py:meth:`generate_sentence`.

        :param int amount:              The amouont of sentences to generate
        :retruns:                       A generator of specified amount tuples
                                        as per :py:meth:`generate_sentence`.
        :rtype:                         generator
        """
        yield self.generate_sentence(**args)
        args['incipit'] = False
        for __ in irange(amount - 1):
            yield self.generate_sentence(**args)

    def generate_paragraph(self, **args):
        """Generates a single paragraph, of random length.

        Also accepts the same arguments as :py:meth:`generate_sentence`.

        :param int paragraph_len:       The length of the paragraph in
                                        sentences. Takes precedence over
                                        paragraph_mean and paragraph_sigma.
        :param float paragraph_mean:    Override the paragraph mean value.
        :param float paragraph_sigma:   Override the paragraph sigma value.
        :returns:                       A tuple containing number of sentences,
                                        number of words, and the paragraph
                                        text.
        :rtype:                         tuple(int, int, str or unicode)
        """
        # The length of the paragraph is a normally distributed random
        # variable.
        mean = args.get('paragraph_mean', self._sample['paragraph_mean'])
        sigma = args.get('paragraph_sigma', self._sample['paragraph_sigma'])
        random_len = int(1 + math.ceil(abs(random.normalvariate(mean, sigma))))
        paragraph_len = args.get('paragraph_len', random_len)

        words_count = 0
        paragraph = list()

        for count, text in self.generate_sentences(paragraph_len, **args):
            words_count += count
            paragraph.append(text)

        # Turn the paragraph into a string.
        return (paragraph_len, words_count, ' '.join(paragraph))

    def generate_paragraphs(self, amount, **args):
        """Generator method that yields paragraphs, of random length.

        Also accepts the same arguments as :py:meth:`generate_paragraph`.

        :param int amount:              The amount of paragraphs to generate.
        :retruns:                       A generator of specified amount tuples.
                                        as per :py:meth:`generate_paragraph`
        :rtype:                         generator
        """
        yield self.generate_paragraph(**args)
        args['incipit'] = False
        for __ in irange(amount - 1):
            yield self.generate_paragraph(**args)
