"""
Train a DNN black box model for the questions dataset.

Also calculate fidelity of LIME explanations when using the RF used for the fidelity experiment
"""

import csv
import os
import pickle
import sys

import numpy as np
import pandas as pd
from keras.callbacks import EarlyStopping
from keras.wrappers.scikit_learn import KerasClassifier
from sklearn.metrics import classification_report, accuracy_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.utils import class_weight

sys.path.insert(1, os.path.join(sys.path[0], '..'))

from DNN_base import TextsToSequences, Padder, create_model

sys.path.insert(0, '..')
from lime.lime_text import LimeTextExplainer
from preprocessing.pre_processing import preProcessing
from statistics import stdev


def calculate_fidelity():
    # Creating an explainer object. We pass the class_names as an argument for prettier display.
    explainer = LimeTextExplainer(class_names=class_names)

    ids = list()
    fidelities = list()

    for i, e in enumerate(X_test):
        print(str(i + 1) + '.', e)

    # for i in range(len(X_test)):
    # we run the fidelity calc only for the first 100 examples
    for i in range(100):
        print('index: ', i)
        # Generate an explanation with at most n features for a random document in the test set.
        idx = i
        exp = explainer.explain_instance(X_test[idx], loaded_model.predict_proba, num_features=10)
        label = pred[i]

        bb_probs = explainer.Zl[:, label].flatten()
        # clip values lower 0 or higher 1 to 0/1
        bb_probs = np.clip(bb_probs, 0, 1)
        print('bb_probs: ', bb_probs)
        lr_probs = explainer.lr.predict(explainer.Zlr)
        lr_probs = np.clip(lr_probs, 0, 1)
        print('lr_probs: ', lr_probs)
        fidelity = np.sum(np.abs(bb_probs - lr_probs) < 0.05) / len(bb_probs)
        print('fidelity: ', fidelity)
        # print('np.sum: ', np.sum(np.abs(bb_probs - lr_probs) < 0.01))
        ids.append(i)
        fidelities.append(fidelity)
        print('')

    fidelity_average = 0

    for i in range(len(ids)):
        print(ids[i])
        print(fidelities[i])
        fidelity_average += fidelities[i]

    print("fidelity average is: ", fidelity_average / len(ids))
    print("fidelity stdev is:", stdev(fidelities))

    with open('../output/LIME_q_DNN.csv', mode='w', newline='') as file:
        writer = csv.writer(file, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        for i in range(len(ids)):
            writer.writerow([ids[i], 'hate speech', 'DNN', fidelities[i]])


df_train = pd.read_csv("../data/question_dataset/question_train.txt", encoding='ISO-8859-1', sep=':',
                       error_bad_lines=False, header=None)
df_test = pd.read_csv("../data/question_dataset/question_test.txt", encoding='ISO-8859-1', sep=':',
                      error_bad_lines=False, header=None)


def remove_first_word(string):
    return string.partition(' ')[2]


df_train.iloc[:, 1] = df_train.iloc[:, 1].apply(remove_first_word)
df_test.iloc[:, 1] = df_test.iloc[:, 1].apply(remove_first_word)

# Which class to define as 0 depends on the distribution of data.
# We pick the class with the largest number of instances. (calculated on question_RF.py)
mapping = {'DESC': 1,
           'ENTY': 0,
           'ABBR': 1,
           'HUM': 1,
           'NUM': 1,
           'LOC': 1}

df_train.iloc[:, 0] = df_train.iloc[:, 0].apply(lambda x: mapping[x])
df_test.iloc[:, 0] = df_test.iloc[:, 0].apply(lambda x: mapping[x])

X_train = df_train.iloc[:, 1].values
y_train = df_train.iloc[:, 0].values
X_test = df_test.iloc[:, 1].values
y_test = df_test.iloc[:, 0].values

X_train = preProcessing(X_train)
X_test = preProcessing(X_test)

X = np.append(X_train, X_test)
y = np.append(y_train, y_test)

X_train, X_test, y_train, y_test = train_test_split(X, y, random_state=42, stratify=y, test_size=0.25)

print(len(X_train))
print(len(X_test))

class_names = ['Entity', 'All other classes']

es = EarlyStopping(monitor='val_loss', mode='min', verbose=1, patience=2)
class_weight = class_weight.compute_class_weight('balanced', np.unique(y_train), y_train)

sequencer = TextsToSequences(num_words=35000)
padder = Padder(140)
myModel = KerasClassifier(build_fn=create_model,
                          epochs=100,
                          validation_split=0.3,
                          class_weight=class_weight,
                          callbacks=[es])

pipeline = make_pipeline(sequencer, padder, myModel)
pipeline.fit(X_train, y_train)

# Save the model to disk
filename = '../models/question_saved_DNN_model.sav'
pickle.dump(pipeline, open(filename, 'wb'))

# Load the model from disk
loaded_model = pickle.load(open(filename, 'rb'))

# Computing interesting metrics/classification report
pred = pipeline.predict(X_test)
# pred = loaded_model.predict(X_test)
print(classification_report(y_test, pred))
print("The accuracy score is {:.2%}".format(accuracy_score(y_test, pred)))

# Following is used to calculate fidelity for all instances using LIME
calculate_fidelity()
