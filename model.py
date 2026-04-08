import pandas as pd
import pickle

from sklearn.feature_extraction.text import CountVectorizer

from sklearn.naive_bayes import MultinomialNB


data=pd.read_csv("complaint_dataset.csv")

cv=CountVectorizer()

X=cv.fit_transform(data["Complaint"])

y=data["Category"]


model=MultinomialNB()

model.fit(X,y)


pickle.dump(model,open("complaint_model.pkl","wb"))

pickle.dump(cv,open("vector.pkl","wb"))
print("Model created successfully")