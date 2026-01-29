#include<bits/stdc++.h>
#include<stdlib.h>
using namespace std;

#define AUTOGUESS true
char guess[6] = "OTHER"; // 统计出的最常出现的5字母单词
#define GUESSNUM 5
#define PRINTALLGUESS false

struct WordScore{
    string word;
    double score;
};
struct Compare {
    bool operator()(const WordScore& a, const WordScore& b) const {
        return a.score > b.score;
    }
};
set<WordScore, Compare> word_score;

class STR {
public:
    char c;
    set<char> whitelist;
    static pair<int, bool> shared_whitelist[26];//first means numbers, second means if number of it is confirmed

    STR();
    static bool shared_all_used();
} str[5] ;
pair<int, bool> STR::shared_whitelist[26];

class NgramScore {
public:
    NgramScore(const string& ngramfile, char sep = ' ');
    double score(const string& text);

private:
    unordered_map<string, double> ngrams;
    size_t L;
    double N;
    double floor;

    void load_ngrams(const string& ngramfile, char sep);
} ngram_score("english_quadgrams.txt");

class TRIE {
public:
    char c;
    TRIE *next[26];
    bool is_end_of_word;

    TRIE(const string& filename = "");
    void insert(const string& word);
    void build_from_file(const string& filename);
} trie("word_list.txt");

void enum_str(int position);
void enum_trie_str(TRIE *node, int position);

int main() {
guessing:
    char input[6] ,result[6];
#if AUTOGUESS
    strcpy(input, guess);
    cout << "I guess is " << input << endl;
#else
    cout << "Please input the word : ";
    cin >> input;
#endif
    cout << "Please input the feedback : ";
    cin >> result;

    int buffer[26] = {0};
    int confirm;
    for(int i = 0; i < 5; i++) {
        switch(result[i]) {
            case '0':
                if(buffer[input[i] - 'A'] == 0)
                    for(int j = 0; j < 5; j++) 
                        str[j].whitelist.erase(input[i]);
                else {
                    STR::shared_whitelist[input[i] - 'A'].first = buffer[input[i] - 'A'];
                    STR::shared_whitelist[input[i] - 'A'].second = true;
                    str[i].whitelist.erase(input[i]);
                }
                break;
            case '1':
                buffer[input[i] - 'A']++;
                str[i].whitelist.erase(input[i]);
                break;
            case '2':
                buffer[input[i] - 'A']++;
                str[i].c = input[i];
                str[i].whitelist.clear();
                str[i].whitelist.insert(input[i]);
                break;
        }
    }

    for(int i = 0; i < 26; i++) {
        if(buffer[i] && !STR::shared_whitelist[i].second) {
            STR::shared_whitelist[i].first = max(buffer[i], STR::shared_whitelist[i].first);
        }
    }

    /**
     * 1. enum_str() is used to enumerate all permutations of 5 characters
     * 2. enum_trie_str() is used to enumerate with trie, only word exists
     */
enum_possible:
    static bool use_trie = true;
    if(use_trie)
        enum_trie_str(&trie, 0);
    else
        enum_str(0);

    if(word_score.size() == 0) {
        if(use_trie) {
            cout << endl << "That's strange, you might have mistyped something..." << endl;
            cout << "+- Can't find your word in the wordlist? Please let me know." << endl;
            cout << "+- Do you want to guess all the permutations of 5 characters? (yes/no)" << endl;
            string option;
            cin >> option;
            if(option == "yes") {
                use_trie = false;
                goto enum_possible;
            }
        }
        else {
            cout << "It seems that you have tried all the permutations of 5 characters." << endl;
            cout << "I'm sure you mistyped something, please check it again." << endl;
        }
        goto exit;
    }

#if AUTOGUESS
    strcpy(guess, word_score.begin()->word.c_str());
#elif PRINTALLGUESS
    cout << "Number of words possible : " << word_score.size() << endl;
    cout << setiosflags(ios::fixed);
    for(auto i : word_score) {
        cout << i.word << " " << setprecision(15) << i.score << endl;
    }
    cout << "------------------------------------------------" << endl;
#else
{
    int count = GUESSNUM;
    cout << GUESSNUM << " guess(es) : " << endl;
    for(auto i : word_score) {
        if(count-- == 0)
            break;
        cout << i.word << " " << setprecision(15) << i.score << endl;
    }
    cout << "------------------------------------------------" << endl;
}
#endif
    if(word_score.size() == 1) {
        cout << "Obviously it is : " << word_score.begin()->word << endl;
        goto exit;
    }


    word_score.clear();
    goto guessing;
    
exit:
    cout << "GOOD GAME" << endl;
    return 0;
}

STR::STR() {
    c = 0;
    for(int i = 0; i < 26; i++) {
        whitelist.insert('A' + i);
    }
    fill(shared_whitelist, shared_whitelist + 26, make_pair(0, false));
}

bool STR::shared_all_used() {
    for(int i = 0; i < 26; i++) {
        if(shared_whitelist[i].first == 0)
            continue;
        if(shared_whitelist[i].second == true)
            return false;
        if(shared_whitelist[i].first > 0)
            return false;
    }
    return true;
}

NgramScore::NgramScore(const string& ngramfile, char sep) {
    load_ngrams(ngramfile, sep);
}

double NgramScore::score(const string& text) {
    double score = 0.0;
    for (size_t i = 0; i <= text.size() - L; ++i) {
        string ngram = text.substr(i, L);
        if (ngrams.find(ngram) != ngrams.end()) {
            score += ngrams[ngram];
        } else {
            score += floor;
        }
    }
    return score;
}

void NgramScore::load_ngrams(const string& ngramfile, char sep) {
    ifstream infile(ngramfile);
    if (!infile) {
        cerr << "Can't open file: " << ngramfile << endl;
        return;
    }

    string line;
    while (getline(infile, line)) {
        size_t sep_pos = line.find(sep);
        if (sep_pos != string::npos) {
            string key = line.substr(0, sep_pos);
            int count = stoi(line.substr(sep_pos + 1));
            ngrams[key] = count;
        }
    }

    infile.close();

    L = ngrams.begin()->first.size();
    N = 0;
    for (const auto& pair : ngrams) {
        N += pair.second;
    }

    for (auto& pair : ngrams) {
        pair.second = log10(pair.second / N);
    }

    floor = log10(0.01 / N);
}

TRIE::TRIE(const string &filename) {
    c = 0;
    is_end_of_word = false;
    fill(begin(next), end(next), nullptr);
    if(filename != "")
        build_from_file(filename);
}

void TRIE::insert(const string& word) {
    TRIE *node = this;
    for (char ch : word) {
        int index = ch - 'A';
        if (!node->next[index]) {
            node->next[index] = new TRIE();
            node->next[index]->c = ch;
        }
        node = node->next[index];
    }
    node->is_end_of_word = true;
}

void TRIE::build_from_file(const string& filename) {
    ifstream infile(filename);
       if (!infile) {
        cerr << "Can't open file: " << filename << endl;
        return;
    }

    string word;
    while (getline(infile, word)) {
        insert(word);
    }

    infile.close();
}

void enum_trie_str(TRIE *node, int position) {
    if(position == 5) {
        if(STR::shared_all_used() == false)
            ;
        else {
            char word[6];
            word[0] = str[0].c;
            word[1] = str[1].c;
            word[2] = str[2].c;
            word[3] = str[3].c;
            word[4] = str[4].c;
            word[5] = '\0';
            string word_str(word);
            double score = ngram_score.score(word_str);
            word_score.insert({word_str, score});
        }
        return ;
    }
    
    for(auto i : node->next) {
        if(i == nullptr)
            ;
        else if(str[position].whitelist.find(i->c) != str[position].whitelist.end()) {
            STR::shared_whitelist[i->c - 'A'].first--;
            str[position].c = i->c;
            enum_trie_str(i, position + 1);
            STR::shared_whitelist[i->c - 'A'].first++;
        }
        else
            ;
    }
    return ;
}

void enum_str(int position) {
    if(position == 5) {
        if(STR::shared_all_used() == false)
            ;
        else {
            char word[6];
            word[0] = str[0].c;
            word[1] = str[1].c;
            word[2] = str[2].c;
            word[3] = str[3].c;
            word[4] = str[4].c;
            word[5] = '\0';
            string word_str(word);
            double score = ngram_score.score(word_str);
            word_score.insert({word_str, score});
        }
        return ;
    }
    
    for(auto v : str[position].whitelist) {
        STR::shared_whitelist[v - 'A'].first--;
        str[position].c = v;
        enum_str(position + 1);
        STR::shared_whitelist[v - 'A'].first++;
    }

    return ;
}