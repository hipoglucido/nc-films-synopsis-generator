import os
import preprocessor
import generator
import settings
import model
from sklearn.externals import joblib
import pickle as pk
import numpy as np
from sklearn.model_selection import train_test_split
import random



def test_generator():

    synopses, genres = load_preprocessed_data(settings.INPUT_PREPROCESSED_FILMS)
    print(synopses[:20])
    print(genres[:20])
    X_train, X_val, y_train, y_val = train_test_split(
        synopses, genres, test_size=settings.VALIDATION_SPLIT, random_state = settings.SEED)
    c= generator.Generator(X_train, y_train)
    c.load_genre_binarizer()
    c.load_indexes()
    #a = g.generate().__next__()
    #g.get_train_val_generators()
    from time import sleep

    while 1:
        for a,b in c.generate():
            print(a[0].shape,a[1].shape,b.shape)
            continue
            for i in range(a[0].shape[0]):
                s = str(c.to_synopsis(a[1][i]))
                if len(s) > 100:
                    print(s)
                continue
                print(c.to_genre(a[0][i]),a[0][i].shape)
                print(c.to_synopsis(a[1][i]),len(a[1][i]),type(a[1][i][0]))
                print(c.index_to_word[b[i]],type(b[i]))
                print('_______________________________________')

            
def generate_files():
    check_nltk_resources()
    check_paths()
    
    p = preprocessor.Preprocessor()
    df = p.load_dataset()
    
    p.preprocess_synopses(df)
    p.preprocess_genres(df)
    p.build_indexes()
    if settings.USE_W2V:
        p.generate_embedding_weights()
    p.filter_dataset()
    p.encode_genres()
    p.encode_synopses()
    p.save_data()

def check_paths():
    if not os.path.exists(settings.DATA_DIR):
        os.makedirs(settings.DATA_DIR)

    if not os.path.exists(settings.OTHERS_DIR):
        os.makedirs(settings.OTHERS_DIR)

    if not os.path.exists(settings.WEIGHTS_DIR):
        os.makedirs(settings.WEIGTHS_DIR)

    if not os.path.exists(settings.TENSORBOARD_LOGS_DIR):
        os.makedirs(settings.TENSORBOARD_LOGS_DIR)

def check_nltk_resources():
    import nltk
    nltk.download('averaged_perceptron_tagger')


def train_network():

    synopses, genres = load_preprocessed_data(settings.INPUT_PREPROCESSED_FILMS)
    X_train, X_val, y_train, y_val = train_test_split(
        synopses, genres, test_size=settings.VALIDATION_SPLIT, random_state = settings.SEED)

    network = model.Network()
    network.load_generators(X_train, X_val, y_train, y_val)       # Synopses and genres as parameter
    
    network.build()
    network.compile()
    network.train()


def load_preprocessed_data(path):
    """
    Loads preprocessed lists of synopses and genres
    """
    films_preprocessed = joblib.load(path)
    genres = films_preprocessed[0]
    synopses = films_preprocessed[1]
    settings.logger.info("Loaded preprocessed films from " + str(path))
    return synopses, genres
    
def get_predictions_greedy(g, n, encoded_genres, previous_words = None):
    from keras.preprocessing import sequence
    if not previous_words:
        previous_words = [g.word_to_index[sample_start(g)]]
    else:
        previous_words = [g.word_to_index[word] for word in previous_words]
    for i in range(settings.MAX_SYNOPSIS_LEN):
        padded_previous_words = sequence.pad_sequences([previous_words], maxlen=settings.MAX_SYNOPSIS_LEN, padding='post', value = g.word_to_index[settings.PAD_TOKEN])
        next_word_probs = n.model.predict([encoded_genres,padded_previous_words])[0]
        sorted_words = np.argsort(next_word_probs)
        best_word = sorted_words[-1]
        previous_words.append(best_word)
        #print(g.to_synopsis(previous_words))
        #print(next_word_probs)
        #print(next_word_probs.sum())
        #print(previous_words.shape)
        #print(encoded_genres.shape)
    previous_words = g.to_synopsis(previous_words)
    return previous_words
    
def sample_start(g):
    s = ['la','el','en','durante','cuando','son','las','eran']*10
    possible_starts = list(g.word_to_index.keys()) + s
    start = random.sample(possible_starts, 1)[0]
    return start
def run_batch_predictions():
    settings.logger.info("Starting batch predictions...")
    n = model.Network()
    n.build()
    n.load_weights()
    g = generator.Generator(None, None)
    g.load_indexes()
    g.load_genre_binarizer()      
    possible_genres = list(g.mlb.classes_) 
    possible_genres = ['Comedia', 'Documental', 'Romance', 'Thriller', 'Acción']
    possible_genres = ['Romance', 'Acción']
    for i in range(1000):
        settings.logger.info("Sample "+str(i)+"________________")
        n_genres = random.randint(1,3)
        input_genres = random.sample(possible_genres, n_genres)
        settings.logger.info("Input genres:"+', '.join(input_genres))
        encoded_genres = g.mlb.transform([input_genres])
        synG = get_predictions_beam(g, n, encoded_genres, 4, ['La'])
        settings.logger.info("BEAM synopsis: "+synG)
        #synb = get_predictions_greedy(g, n, encoded_genres)
        #settings.logger.info("GREEDY synopsis: "+synb)
        
def get_predictions_beam(g, n, encoded_genres, beam_size = None, previous_words = None):
    from keras.preprocessing import sequence
    if not beam_size:
        beam_size = int(input("Introduce an integer for the beamsize: "))
    
    model = n.model
    if not previous_words:
        start = [g.word_to_index[sample_start(g)]]
    else:
        start = [g.word_to_index[word] for word in previous_words]
    synopses = [[start,0.0]]
    while(len(synopses[0][0]) < 60):
        temp_synopses = []
        for synopsis in synopses:
            partial_synopsis = sequence.pad_sequences([synopsis[0]], maxlen=settings.MAX_SYNOPSIS_LEN, padding='post', value = g.word_to_index[settings.PAD_TOKEN])
            next_words_pred = model.predict([encoded_genres, np.asarray(partial_synopsis)])[0]
            next_words = np.argsort(next_words_pred)[-beam_size:]
            for word in next_words:
                new_partial_synopsis, new_partial_synopsis_prob = synopsis[0][:], synopsis[1]
                new_partial_synopsis.append(word)
                new_partial_synopsis_prob+=next_words_pred[word]
                temp_synopses.append([new_partial_synopsis,new_partial_synopsis_prob])
        synopses = temp_synopses
        synopses.sort(key = lambda l:l[1])
        synopses = synopses[-beam_size:]
    synopses = g.to_synopsis(synopses[-1][0])
    return synopses
def validation_bleu():
    
    import nltk
    import pandas as pd

    n = model.Network()
    n.build()
    n.load_weights()
    g = generator.Generator(None, None)
    g.load_indexes()
    g.load_genre_binarizer()
    synopses, genres = load_preprocessed_data(settings.INPUT_PREPROCESSED_FILMS)
    _, tsynopses, _,  tgenres = train_test_split(
        synopses, genres, test_size=settings.VALIDATION_SPLIT, random_state = settings.SEED)
    
    preds = [
        'Conjunto que tres no que se acerca a la vida de un grupo de personas en distintas edades y no y que están porque por <unk> situaciones . <eos>',
        'Una pareja muere sola sin una isla . Él pesca con su barco y y es ama de casa . <eos>',
        'Serie de TV . DIGITO llega . lo episodios . Serie que continúa las aventuras del en <unk> en el lejano este . <eos>'
    ]
 
    help_words = 3
    beam_size = 4
    mode = 'b'
    references = []
    hypotheses = []
    
    predictions = []
    
    total = len(tsynopses)
    i = 0
    filename = 'Preds_'+settings.WEIGHTS_PATH.split('STM_')[1].split('.hdf')[0]+'_h'+str(help_words)+'.csv'
    settings.logger.info("Computing CORPUS BLEU SCORE for "+str(total)+" synopses...")
    for ts, tg in zip(tsynopses, tgenres):
        i += 1
        prediction = {}
        ts = ts[:settings.MAX_SYNOPSIS_LEN]
        tsw = g.to_synopsis(ts)
        #p = ' '.join(p.split()[:settings.MAX_SYNOPSIS_LEN])
        settings.logger.info("_________________________"+str(100*i/total)[:4]+'%')
        prediction['Genre'] = g.to_genre(tg)
        settings.logger.info("Genres: "+prediction['Genre'])
        prediction['Original'] = tsw
        settings.logger.info("True synopsis: "+prediction['Original'])
        encoded_genres = np.array([tg])
        previous_words = tsw.split()[:help_words]

        settings.logger.info("Help words: "+str(previous_words))
        if mode == 'g':
            psynopsis = get_predictions_greedy(g, n, encoded_genres, previous_words)
            #psynopsis =  p
        else:
            psynopsis = get_predictions_beam(g, n, encoded_genres, beam_size, previous_words)
        prediction['Prediction'] = psynopsis   
        predictions.append(prediction)
        settings.logger.info("Pred synopsis: "+psynopsis)
        references.append(tsw.split())
        hypotheses.append(psynopsis.split())
        current_score = nltk.translate.bleu_score.corpus_bleu(references, hypotheses)
        prediction['Current_BLEU'] = current_score 
        settings.logger.info("current BLEU score: "+str(prediction['Current_BLEU']))
        pd.DataFrame(predictions).to_csv(os.path.join(settings.PREDICTIONS_DIR,filename))
    final_score = current_score
    settings.logger.info("final BLEU score: "+str(final_score))

def get_predictions(g, n):
    possible_genres = list(g.mlb.classes_)
    print("Possible film genres: ",','.join(possible_genres)) 
    input_line = 'r'#input("Insert a comma separated set of genres (r for random, q for quit): ")
    if input_line == 'q':
        exit()
    randomly = input_line == 'r'
    p = preprocessor.Preprocessor()
    if randomly:
        n_genres = random.randint(1,6)
        input_genres = random.sample(possible_genres, n_genres)
    else:
        input_genres = input_line.split(',')
        for ig in input_genres:
            if ig not in possible_genres:
                print(ig + " is not a possible genre")
                get_predictions(g, n)
    print("Input genres: ",', '.join(input_genres))
    encoded_genres = g.mlb.transform([input_genres])
    mode = input("Input g or b for greedy or beam search mode: ")
    previous_words = input("Introduce help/previous words (optional): ")
    previous_words = p.clean_text(previous_words)
    previous_words = p.tokenize(previous_words)[:-1]
    prvs = []
    for pw in previous_words:
        if pw in g.word_to_index.keys():
            prvs.append(pw)
        else:
            prvs.append(settings.UNKNOWN_TOKEN)
    if previous_words == '':
        previous_words = None
    print("Starting words: "+str(previous_words))
    if mode == 'g':
        print("Greedy search mode")
        syn = get_predictions_greedy(g, n, encoded_genres, previous_words)
    elif mode == 'b':
        print("Beam search mode")
        syn = get_predictions_beam(g=g, n=n, encoded_genres=encoded_genres, previous_words=previous_words)
    else:
        print("Wrong mode")
        get_predictions(g, n)
    print("Synopsis: ",syn)
    get_predictions(g, n)
    
def interface():
    settings.logger.info("Starting user interface...")
    n = model.Network()
    n.build()
    n.load_weights()
    g = generator.Generator(None, None)
    g.load_indexes()
    g.load_genre_binarizer()
    get_predictions(g, n)

if __name__ == '__main__':

    #generate_files()
    #test_generator()
    #train_network()
    #validation_bleu()
    interface()
    #run_batch_predictions()
    #validation_bleu()

